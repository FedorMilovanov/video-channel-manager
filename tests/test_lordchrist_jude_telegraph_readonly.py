"""The Jude probe is a bounded account read, never a publication authority."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from video_channel_manager import lordchrist_jude_telegraph_readonly as probe

ROOT = Path(__file__).resolve().parents[1]
MAIN_SHA = "a" * 40
STATE_SHA = "b" * 40
SECRET = "test-token-never-output"


def anchor() -> dict:
    return {
        "schema_name": "video-channel-manager.lordchrist-telegraph-ledger",
        "schema_version": 1,
        "project_key": "lord-god-strength",
        "entries": {
            probe.ANCHOR_PUBLICATION_ID: {
                "publication_id": probe.ANCHOR_PUBLICATION_ID,
                "state": "published",
                "provider_effect": "verified",
                "telegram_provider_effect": "verified",
                "telegram_chat_id": -1001295216957,
                "telegram_message_id": 1619,
                "telegraph_path": probe.ANCHOR_PATH,
                "telegraph_url": "https://telegra.ph/" + probe.ANCHOR_PATH,
            }
        },
    }


def page(path: str, title: str) -> dict:
    return {"path": path, "url": "https://telegra.ph/" + path, "title": title}


def fake_api(
    first: list[dict],
    second: list[dict] | None = None,
    *,
    account_counts: list[int] | None = None,
    mutate_reply=None,
):
    second = first if second is None else second
    calls: list[tuple[str, dict[str, list[str]]]] = []
    list_call = 0
    count_call = 0
    pages_per_snapshot = (len(first) + probe.PAGE_LIMIT - 1) // probe.PAGE_LIMIT

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal list_call, count_call
        assert request.method == "POST"  # GET-like API reads, token only in form body
        assert request.url.host == "api.telegra.ph"
        assert not request.url.query
        method = request.url.path.removeprefix("/")
        assert method in {"getAccountInfo", "getPageList"}
        form = parse_qs(request.content.decode())
        assert form.pop("access_token") == [SECRET]
        calls.append((method, form))
        if method == "getAccountInfo":
            assert json.loads(form["fields"][0]) == ["page_count"]
            counts = account_counts or [len(first)] * 3
            result = {"page_count": counts[count_call]}
            count_call += 1
        else:
            snapshot = first if list_call < pages_per_snapshot else second
            list_call += 1
            offset = int(form["offset"][0])
            limit = int(form["limit"][0])
            assert limit == probe.PAGE_LIMIT
            result = {"total_count": len(snapshot), "pages": copy.deepcopy(snapshot[offset : offset + limit])}
        if mutate_reply is not None:
            result = mutate_reply(method, result, len(calls))
        return httpx.Response(200, json={"ok": True, "result": result})

    return httpx.Client(transport=httpx.MockTransport(handle)), calls


def run(client: httpx.Client, *, ledger=None, root: Path = ROOT, token: str = SECRET) -> dict:
    return probe.inspect_account(
        client=client,
        token=token,
        ledger=anchor() if ledger is None else ledger,
        repo_root=root,
        main_sha=MAIN_SHA,
        state_sha=STATE_SHA,
    )


def test_complete_double_paginated_listing_is_narrow_and_never_discloses_other_pages() -> None:
    pages = [page(probe.ANCHOR_PATH, "Known anchor")]
    pages += [page(f"other-{i}", f"Private unrelated title {i}") for i in range(235)]
    client, calls = fake_api(pages)
    report = run(client)
    assert [method for method, _ in calls] == [
        "getAccountInfo",
        "getPageList",
        "getPageList",
        "getAccountInfo",
        "getPageList",
        "getPageList",
        "getAccountInfo",
    ]
    assert report["account_page_count"] == 236
    assert report["exact_title_matches"] == 0
    assert report["possible_related_title_matches"] == 0
    assert report["ledger_status"] == "no_entry"
    assert report["two_consistent_account_scans"] is True
    assert report["provider_write_performed"] is False
    assert report["publication_authorized"] is False
    assert report["main_sha"] == MAIN_SHA and report["state_sha"] == STATE_SHA
    output = json.dumps(report, ensure_ascii=False)
    assert SECRET not in output and "Private unrelated" not in output and "other-0" not in output
    assert probe.ANCHOR_PATH not in output


def test_exact_and_related_titles_are_counts_only_not_proof_of_absence() -> None:
    pages = [
        page(probe.ANCHOR_PATH, "Known anchor"),
        page("exact-11-22", probe.EXPECTED_TITLE),
        page("near-11-22", "Два чтения — Иуда 1:5"),
        page("english-11-22", "Jude 5: Jesus and the Exodus"),
        page("normalized-11-22", probe.EXPECTED_TITLE.upper()),
        page("unrelated-11-22", "Иуда Искариот"),
    ]
    client, _ = fake_api(pages)
    report = run(client)
    assert report["exact_title_matches"] == 1
    assert report["possible_related_title_matches"] == 3
    assert report["scan_scope"] == "single_owned_account_titles_only"
    assert report["other_accounts_checked"] is False
    assert report["page_contents_checked"] is False
    assert report["telegram_history_checked"] is False
    assert report["publication_authorized"] is False
    output = json.dumps(report, ensure_ascii=False)
    assert "exact-11-22" not in output and "Два чтения" not in output and SECRET not in output


def test_ledger_entry_is_reported_as_present_even_when_not_terminal() -> None:
    ledger = anchor()
    ledger["entries"][probe.PUBLICATION_ID] = {"state": "page_dispatch_claimed"}
    client, _ = fake_api([page(probe.ANCHOR_PATH, "anchor")])
    report = run(client, ledger=ledger)
    assert report["ledger_status"] == "entry_present_reconcile"
    assert report["publication_authorized"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_name", "wrong"),
        ("schema_version", 2),
        ("project_key", "another-project"),
        ("entries", []),
    ],
)
def test_wrong_ledger_identity_stops_before_any_provider_read(field: str, value) -> None:
    ledger = anchor()
    ledger[field] = value
    client, calls = fake_api([page(probe.ANCHOR_PATH, "anchor")])
    with pytest.raises(probe.ProbeError):
        run(client, ledger=ledger)
    assert calls == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("state", "pending"),
        ("provider_effect", "may_exist"),
        ("telegram_provider_effect", "unknown"),
        ("telegram_chat_id", -1003345085810),
        ("telegram_message_id", 1),
        ("telegraph_path", "other"),
        ("telegraph_url", "https://telegra.ph/other"),
        ("publication_id", "other"),
    ],
)
def test_anchor_must_be_exact_previously_verified_channel_receipt(field: str, value) -> None:
    ledger = anchor()
    ledger["entries"][probe.ANCHOR_PUBLICATION_ID][field] = value
    client, calls = fake_api([page(probe.ANCHOR_PATH, "anchor")])
    with pytest.raises(probe.ProbeError):
        run(client, ledger=ledger)
    assert calls == []


def test_owned_page_anchor_must_actually_appear_in_both_scans() -> None:
    client, _ = fake_api([page("another-account", "unrelated")])
    with pytest.raises(probe.ProbeError, match="anchor"):
        run(client)


def test_missing_token_and_malformed_shas_stop_before_http() -> None:
    client, calls = fake_api([page(probe.ANCHOR_PATH, "anchor")])
    with pytest.raises(probe.ProbeError):
        run(client, token=" ")
    with pytest.raises(probe.ProbeError):
        probe.inspect_account(
            client=client, token=SECRET, ledger=anchor(), repo_root=ROOT, main_sha="main", state_sha=STATE_SHA
        )
    assert calls == []


def test_same_count_but_changed_titles_between_scans_is_not_a_stable_snapshot() -> None:
    first = [page(probe.ANCHOR_PATH, "anchor"), page("changing", "One")]
    second = [page(probe.ANCHOR_PATH, "anchor"), page("changing", "Two")]
    client, _ = fake_api(first, second)
    with pytest.raises(probe.ProbeError, match="changed"):
        run(client)


def test_account_count_change_mid_scan_fails_closed() -> None:
    client, _ = fake_api([page(probe.ANCHOR_PATH, "anchor")], account_counts=[1, 2, 2])
    with pytest.raises(probe.ProbeError, match="changed"):
        run(client)


@pytest.mark.parametrize("bad_count", [-1, True, "1", probe.MAX_ACCOUNT_PAGES + 1])
def test_bad_or_unbounded_account_count_is_rejected(bad_count) -> None:
    client, _ = fake_api([page(probe.ANCHOR_PATH, "anchor")], account_counts=[bad_count, 1, 1])
    with pytest.raises(probe.ProbeError):
        run(client)


@pytest.mark.parametrize(
    "bad_page",
    [
        {"path": "x", "url": "https://telegra.ph/x", "title": None},
        {"path": "../x", "url": "https://telegra.ph/../x", "title": "bad"},
        {"path": "x", "url": "https://attacker.example/x", "title": "bad"},
        {"path": "x", "url": "https://telegra.ph/x?token=x", "title": "bad"},
        "not-a-page",
    ],
)
def test_malformed_page_entries_fail_the_whole_scan(bad_page) -> None:
    client, _ = fake_api([page(probe.ANCHOR_PATH, "anchor"), bad_page])
    with pytest.raises(probe.ProbeError):
        run(client)


def test_duplicate_paths_and_short_page_lists_fail_closed() -> None:
    same = page(probe.ANCHOR_PATH, "anchor")
    client, _ = fake_api([same, same])
    with pytest.raises(probe.ProbeError):
        run(client)

    def truncate(method, result, _number):
        if method == "getPageList":
            result["pages"] = []
        return result

    client, _ = fake_api([same], mutate_reply=truncate)
    with pytest.raises(probe.ProbeError):
        run(client)


def test_provider_errors_are_redacted_and_do_not_follow_redirects() -> None:
    def error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "https://attacker.example/" + SECRET})

    client = httpx.Client(transport=httpx.MockTransport(error), follow_redirects=True)
    with pytest.raises(probe.ProbeError) as caught:
        run(client)
    assert SECRET not in str(caught.value)


def test_exact_jude_article_cover_queue_and_binding_are_read_only_preconditions(tmp_path: Path) -> None:
    paths = [
        probe.QUEUE_PATH,
        probe.ARTICLE_PATH,
        probe.COVER_PATH,
        probe.PROFILE_PATH,
        probe.BINDING_PATH,
    ]
    for relative in paths:
        dest = tmp_path / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, dest)
    client, calls = fake_api([page(probe.ANCHOR_PATH, "anchor")])
    with (tmp_path / probe.ARTICLE_PATH).open("ab") as changed:
        changed.write(b" ")
    with pytest.raises(probe.ProbeError):
        run(client, root=tmp_path)
    assert calls == []


def test_static_contract_uses_no_provider_write_endpoint() -> None:
    text = (ROOT / "src/video_channel_manager/lordchrist_jude_telegraph_readonly.py").read_text(encoding="utf-8")
    for forbidden in ("/createPage", "/editPage", "/sendMessage", "/deleteMessage", "revokeAccessToken"):
        assert forbidden not in text
