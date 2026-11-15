from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest


SRC = Path(__file__).parents[1] / "scripts" / "youtube_exact_video_metadata_repair.py"
SPEC = importlib.util.spec_from_file_location("youtube_exact_metadata", SRC)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def raw():
    return {
        "id": "Ba-1IHVz3H8",
        "snippet": {
            "channelId": "UCeSJsC6go2c9pdJCuUI1BYA",
            "title": "Действительно ли Вы Знаете Господа? - Пол Вошер",
            "description": "Full verified description\n00:00 First chapter",
            "tags": ["John MacArthur", "Shepherds Conference"],
            "categoryId": "27",
            "defaultLanguage": "ru",
            "defaultAudioLanguage": "ru",
        },
        "status": {
            "uploadStatus": "processed",
            "privacyStatus": "public",
            "license": "creativeCommon",
            "embeddable": True,
            "publicStatsViewable": True,
            "selfDeclaredMadeForKids": False,
            "madeForKids": False,
        },
        "contentDetails": {"duration": "PT51M28S", "hasCustomThumbnail": True},
        "localizations": {"ru": {"title": "Русский заголовок"}, "en-US": {"title": "English title"}},
    }


def plan_from(raw_video):
    before = module.observed(raw_video)
    after = {
        "tags": [
            "Пол Вошер",
            "Paul Washer",
            "Проповедь",
            "Христианство",
            "Покаяние",
            "Евангелие",
            "Обращение",
            "Библия",
            "Бог",
            "Иисус Христос",
        ],
        "license": "youtube",
    }
    return {
        "schema": "youtube-exact-metadata-repair-v1",
        "account": "fedor-milovanov",
        "channel_id": before["channel_id"],
        "video_id": before["video_id"],
        "before": before,
        "after": after,
        "before_sha256": module.digest(before),
        "after_sha256": module.digest(after),
    }


class FakeWriter:
    def __init__(self, video):
        self.video = video
        self.requests = []

    def _request(self, method, resource, *, params, json_body=None, require_write=False):
        self.requests.append((method, resource, copy.deepcopy(json_body), require_write))
        if method == "GET":
            return {"items": [copy.deepcopy(self.video)]}
        assert require_write and method == "PUT" and resource == "videos"
        assert params["part"] == "snippet,status"
        assert json_body["id"] == self.video["id"]
        self.video["snippet"].update(json_body["snippet"])
        self.video["status"].update(json_body["status"])
        return copy.deepcopy(self.video)


def test_plan_rejects_cross_channel_and_cross_speaker_tags():
    p = plan_from(raw())
    module.validate_plan(p)
    p["channel_id"] = "wrong"
    with pytest.raises(ValueError, match="Wrong owner"):
        module.validate_plan(p)
    p = plan_from(raw())
    p["after"]["tags"].append("John MacArthur")
    p["after_sha256"] = module.digest(p["after"])
    with pytest.raises(ValueError, match="Cross-speaker"):
        module.validate_plan(p)


def test_mismatch_in_description_privacy_or_localization_refuses_get_only():
    for field in ("description", "privacyStatus", "localizations"):
        source = raw()
        plan = plan_from(source)
        live = copy.deepcopy(source)
        if field == "description":
            live["snippet"]["description"] += " manual edit"
        elif field == "privacyStatus":
            live["status"]["privacyStatus"] = "private"
        else:
            live["localizations"]["en-US"]["title"] += " changed"
        writer = FakeWriter(live)
        with pytest.raises(ValueError, match="Owner state mismatch"):
            module.execute(
                plan, writer, account="fedor-milovanov", channel="UCeSJsC6go2c9pdJCuUI1BYA", execute_write=False
            )
        assert all(m[0] == "GET" for m in writer.requests)


def test_dry_run_only_reads():
    v = raw()
    writer = FakeWriter(v)
    p = plan_from(v)
    result = module.execute(
        p, writer, account="fedor-milovanov", channel="UCeSJsC6go2c9pdJCuUI1BYA", execute_write=False
    )
    assert result["status"] == "dry_run_verified"
    assert len(writer.requests) == 1 and writer.requests[0][0] == "GET"


def test_update_body_leaves_description_and_status_identity_untouched():
    video = raw()
    tags = plan_from(video)["after"]["tags"]
    body = module.update_body(video, tags=tags, license="youtube")
    assert body["snippet"]["title"] == video["snippet"]["title"]
    assert body["snippet"]["description"] == video["snippet"]["description"]
    assert body["snippet"]["defaultAudioLanguage"] == "ru"
    assert body["status"]["privacyStatus"] == "public"
    assert body["status"]["selfDeclaredMadeForKids"] is False
    assert "uploadStatus" not in body["status"] and "madeForKids" not in body["status"]
    assert body["status"]["license"] == "youtube"


def test_after_readback_guards_every_unchanged_field():
    v = raw()
    plan = plan_from(v)
    v2 = copy.deepcopy(v)
    v2["snippet"]["tags"] = plan["after"]["tags"]
    v2["status"]["license"] = "youtube"
    module.validate_live(plan, v2, after=True)
    v2["contentDetails"]["hasCustomThumbnail"] = False
    with pytest.raises(ValueError, match="has_custom_thumbnail"):
        module.validate_live(plan, v2, after=True)


class LiveFakeWriter(FakeWriter):
    def __init__(self, video, data_dir, *, fail_put=False):
        super().__init__(video)
        self.token_store = type("Store", (), {"data_dir": data_dir})()
        self.fail_put = fail_put

    def _request(self, method, resource, *, params, json_body=None, require_write=False):
        if method == "PUT" and self.fail_put:
            self.requests.append((method, resource, None, require_write))
            raise RuntimeError("Simulated ambiguous HTTP response")
        return super()._request(method, resource, params=params, json_body=json_body, require_write=require_write)


def test_guarded_execution_preserves_contents_and_writes_exactly_once(tmp_path: Path):
    v = raw()
    p = plan_from(v)
    writer = LiveFakeWriter(v, tmp_path)
    backup = tmp_path / "metadata-original.json"
    receipt = tmp_path / "metadata-result.json"
    result = module.execute(
        p,
        writer,
        account="fedor-milovanov",
        channel="UCeSJsC6go2c9pdJCuUI1BYA",
        execute_write=True,
        backup_path=backup,
        receipt_path=receipt,
    )
    assert result["status"] == "completed_live_verified"
    assert [x[0] for x in writer.requests] == ["GET", "PUT", "GET"]
    assert backup.is_file() and receipt.is_file()
    assert writer.video["snippet"]["description"] == v["snippet"]["description"]
    assert writer.video["status"]["privacyStatus"] == "public"
    assert writer.video["status"]["license"] == "youtube"
    assert writer.video["localizations"] == v["localizations"]
    with pytest.raises(ValueError, match="journals"):
        module.execute(
            p,
            writer,
            account="fedor-milovanov",
            channel="UCeSJsC6go2c9pdJCuUI1BYA",
            execute_write=True,
            backup_path=backup,
            receipt_path=receipt,
        )


def test_ambiguous_mutation_not_retried_and_journal_kept(tmp_path: Path):
    v = raw()
    p = plan_from(v)
    writer = LiveFakeWriter(v, tmp_path, fail_put=True)
    backup = tmp_path / "backup.json"
    receipt = tmp_path / "receipt.json"
    with pytest.raises(RuntimeError, match="ambiguous"):
        module.execute(
            p,
            writer,
            account="fedor-milovanov",
            channel="UCeSJsC6go2c9pdJCuUI1BYA",
            execute_write=True,
            backup_path=backup,
            receipt_path=receipt,
        )
    assert [x[0] for x in writer.requests] == ["GET", "PUT"]
    assert backup.is_file()
    state = __import__("json").loads(receipt.read_text(encoding="utf-8"))
    assert state["status"] == "pending_reconciliation"
    assert state["provider_writes_attempted"] == 1


def test_youtube_reorders_tags_without_changing_membership() -> None:
    source = raw()
    plan = plan_from(source)
    live = copy.deepcopy(source)
    live["snippet"]["tags"] = sorted(plan["after"]["tags"], key=str.casefold)
    live["status"]["license"] = "youtube"
    assert live["snippet"]["tags"] != plan["after"]["tags"]
    module.validate_live(plan, live, after=True)
    # Real metadata drift must still fail: no extra, dropped or duplicated tags.
    live["snippet"]["tags"] = live["snippet"]["tags"][:-1]
    with pytest.raises(ValueError, match="tags"):
        module.validate_live(plan, live, after=True)
    live["snippet"]["tags"] = list(plan["after"]["tags"])
    live["snippet"]["tags"][-1] = live["snippet"]["tags"][0]
    with pytest.raises(ValueError, match="tags"):
        module.validate_live(plan, live, after=True)
