"""Fail-closed, one-page-at-a-time corrections for existing Charnock Telegraph pages.

No new pages, channel posts, queue edits or credentials in logs/receipts.
Default action is public GET + dry-run; execution requires an existing account
token, an explicit confirmation and an outside-repository receipt directory.
This cannot make Telegraph's editPage atomic: an edit may race between the
last GET and POST; a failed/ambiguous POST must never be retried blindly.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

HOST = "https://api.telegra.ph"
CONFIRM = "EDIT_EXISTING_CHARNOCK_PAGE_ONCE"
AUTHOR = "Господь Бог"
AUTHOR_URL = "https://t.me/lordchrist"
MAX_RESPONSE = 1_500_000
# 17 Nov 2026 public getPage?return_content=true, canonical JSON of content.
CONTRACTS = {
    "03": {
        "path": "Tri-vozrazheniya-ateista-predanie-zagovor-pravitelej-strah--ispravlennoe-izdanie-11-05",
        "title": "Три возражения атеиста: предание, заговор правителей, страх — исправленное издание",
        "nodes": 130,
        "sha256": "6f1a9ca861f56f25020fdc9011c8080e37ccae1b661390230fa2cfcecdee6c34",
        "indices": (104,),
    },
    "history-01": {
        "path": "Um-kotoryj-ne-toropilsya-Stiven-CHarnok-i-glubina-mysli-v-ehpohu-bystryh-otvetov--ispravlennoe-izdanie-11-05",
        "title": "Как познание Бога, о Котором писал Чарнок, меняет веру, поклонение и повседневную жизнь христианина в XXI веке?",
        "nodes": 76,
        "sha256": "d7a8b054db90317851cb3c523c572a8e93ac2d7b72b68ff4fe6c40f68b3952b3",
        "indices": (8, 15, 23, 31, 38, 45),
    },
}

OLD_Q29 = (
    "Тогда как Писание говорит: «Страх Господень есть начало премудрости» — или всей религии; "
    "это понимается не как смущённый и ужасающий страх перед Ним по причине Его святости, "
    "а как поклонение Ему, покорность Ему и искреннее искание Его."
)
NEW_Q29 = (
    "Когда Писание говорит: «Страх Господень есть начало премудрости» — или всей религии, — "
    "имеется в виду не смятенный, ужасающий страх, а благоговейный страх перед Ним ввиду Его святости: "
    "поклонение Ему, покорность Ему и искреннее искание Его."
)
OLD_BIRTH = "Чарнок родился в Лондоне в 1628 году."
NEW_BIRTH = (
    "Энтони Вуд в биографическом свидетельстве 1691 года сообщает, что Чарнок родился в Лондоне. "
    "Часто указываемый 1628 год является приблизительной датой, выведенной из сведений о возрасте; "
    "запись о рождении или крещении пока не установлена."
)
CREDIT_ENDING = " (беседа I)"
EXPECTED_ROMANS = {15: "I", 23: "II", 31: "V", 38: "VIII", 45: "IX"}


class UnsafeRevision(RuntimeError):
    """The live page does not match the reviewed one-shot contract."""


def sha_content(nodes: Any) -> str:
    normalized = json.dumps(nodes, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def checked_page(page: dict[str, Any], key: str) -> None:
    spec = CONTRACTS[key]
    for k, value in (("path", spec["path"]), ("title", spec["title"]), ("author_name", AUTHOR), ("author_url", AUTHOR_URL)):
        if page.get(k) != value:
            raise UnsafeRevision(f"{key}: unreviewed {k}, no mutation")
    content = page.get("content")
    if not isinstance(content, list) or len(content) != spec["nodes"]:
        raise UnsafeRevision(f"{key}: unexpected content structure, no mutation")
    if sha_content(content) != spec["sha256"]:
        raise UnsafeRevision(f"{key}: content SHA changed; reconcile live edits first")


def prepare(page: dict[str, Any], key: str) -> dict[str, Any]:
    """Produce a complete page clone with ONLY pinned replacements."""
    checked_page(page, key)
    proposal = copy.deepcopy(page)
    nodes = proposal["content"]
    if key == "03":
        node = nodes[104]
        if node != {"tag": "blockquote", "children": [OLD_Q29]}:
            raise UnsafeRevision("03: q-29 old node unexpectedly differs")
        node["children"] = [NEW_Q29]
    elif key == "history-01":
        birth = nodes[8]
        if birth.get("tag") != "p" or not isinstance(birth.get("children"), list):
            raise UnsafeRevision("history-01: unexpected birth node")
        children = birth["children"]
        if (len(children) != 3 or not isinstance(children[0], str) or
                children[1] != {"tag": "em", "children": ["феллоу"]} or
                not isinstance(children[2], str) or not children[0].startswith(OLD_BIRTH)):
            raise UnsafeRevision("history-01: birth structure/content differs")
        children[0] = NEW_BIRTH + children[0][len(OLD_BIRTH):]
        for index, roman in EXPECTED_ROMANS.items():
            node = nodes[index]
            if node.get("tag") != "p" or not isinstance(node.get("children"), list):
                raise UnsafeRevision(f"history-01: credit {index} structure differs")
            if len(node["children"]) != 1 or not isinstance(node["children"][0], dict):
                raise UnsafeRevision(f"history-01: credit {index} nesting differs")
            inner = node["children"][0]
            if inner.get("tag") != "em" or not isinstance(inner.get("children"), list) or len(inner["children"]) != 1:
                raise UnsafeRevision(f"history-01: credit {index} italic structure differs")
            value = inner["children"][0]
            if (not isinstance(value, str) or not value.endswith(CREDIT_ENDING) or
                    f"беседа {roman} «" not in value):
                raise UnsafeRevision(f"history-01: credit {index} attribution differs")
            inner["children"][0] = value[:-len(CREDIT_ENDING)]
    else:
        raise UnsafeRevision("Unexpected article key")

    changed = tuple(i for i, (before, after) in enumerate(zip(page["content"], nodes)) if before != after)
    if changed != CONTRACTS[key]["indices"] or len(nodes) != len(page["content"]):
        raise UnsafeRevision(f"{key}: unexpected changed-node set: {changed}")
    for field in ("path", "title", "author_name", "author_url"):
        if proposal[field] != page[field]:
            raise UnsafeRevision(f"{key}: metadata unexpectedly changed")
    return proposal


def _json_result(data: bytes, operation: str) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, ValueError):
        raise UnsafeRevision(f"{operation}: invalid JSON") from None
    if not isinstance(value, dict) or value.get("ok") is not True or not isinstance(value.get("result"), dict):
        raise UnsafeRevision(f"{operation}: provider rejected or malformed result")
    return value["result"]


def _read(req: Request) -> bytes:
    with urlopen(req, timeout=20) as response:
        result = response.read(MAX_RESPONSE + 1)
    if len(result) > MAX_RESPONSE:
        raise UnsafeRevision("Provider response exceeded size bound")
    return result


def _multipart(fields: dict[str, str]) -> tuple[str, bytes]:
    boundary = "charnock-" + secrets.token_hex(16)
    out = bytearray()
    for name, value in fields.items():
        if not re.fullmatch(r"[a-z_]+", name):
            raise UnsafeRevision("Invalid multipart field")
        out.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n".encode())
        out.extend(value.encode("utf-8"))
        out.extend(b"\r\n")
    out.extend(f"--{boundary}--\r\n".encode())
    return f"multipart/form-data; boundary={boundary}", bytes(out)


def post_form(path: str, fields: dict[str, str]) -> dict[str, Any]:
    if not path.startswith(("getPage/", "getPageList", "editPage/")):
        raise UnsafeRevision("Unexpected Telegraph operation")
    mime, data = _multipart(fields)
    req = Request(HOST + "/" + path, data=data, headers={"Content-Type": mime}, method="POST")
    return _json_result(_read(req), path.split("/")[0])


def get_public_page(path: str) -> dict[str, Any]:
    url = HOST + "/getPage/" + quote(path, safe="-") + "?return_content=true"
    page = _json_result(_read(Request(url, headers={"User-Agent":"Charnock-Revision-Readback/1.0"})), "getPage")
    return page


def verify_ownership(token: str, path: str) -> None:
    info = post_form("getPage/" + path, {"access_token": token, "return_content": "false"})
    if info.get("path") != path or info.get("can_edit") is False:
        raise UnsafeRevision("Account cannot edit this exact existing page")
    if info.get("can_edit") is True:
        return
    for offset in range(0, 2000, 200):
        data = post_form("getPageList", {"access_token": token, "offset": str(offset), "limit": "200"})
        pages = data.get("pages")
        if not isinstance(pages, list):
            raise UnsafeRevision("Cannot verify account ownership")
        if any(isinstance(p, dict) and p.get("path") == path for p in pages):
            return
        if len(pages) < 200:
            break
    raise UnsafeRevision("Exact page is not in account-owned page list")


def run_one(key: str, *, execute: bool, confirm: str | None, receipt_dir: Path | None) -> dict[str, Any]:
    path = CONTRACTS[key]["path"]
    before = get_public_page(path)
    after = prepare(before, key)
    proposal_sha = sha_content(after["content"])
    result: dict[str, Any] = {
        "article": key, "path": path, "old_sha256": sha_content(before["content"]),
        "new_sha256": proposal_sha, "changed_nodes": list(CONTRACTS[key]["indices"]),
        "node_count": len(before["content"]), "effect": "DRY_RUN_NO_POST"
    }
    if not execute:
        return result
    if confirm != CONFIRM or receipt_dir is None:
        raise UnsafeRevision("Execution requires explicit confirmation and outside-repository receipt directory")
    if not receipt_dir.is_dir() or any((part / ".git").exists() for part in (receipt_dir, *receipt_dir.parents)):
        raise UnsafeRevision("Receipt directory must already exist outside a git repository")
    receipt_file = receipt_dir / f"charnock-telegraph-{key}-{proposal_sha[:16]}.json"
    if receipt_file.exists():
        raise UnsafeRevision("Receipt already exists; reconcile first, no POST")
    token = os.environ.get("LORDCHRIST_TELEGRAPH_ACCESS_TOKEN", "").strip()
    if not token:
        raise UnsafeRevision("Existing Telegraph access token unavailable; no provider edit attempted")
    verify_ownership(token, path)
    # Second live GET guards against any intervening manual or agent edit.
    recheck = get_public_page(path)
    checked_page(recheck, key)
    if sha_content(recheck["content"]) != result["old_sha256"]:
        raise UnsafeRevision("Live snapshot changed before edit; no POST")
    # One irreversible POST only. Any timeout/error makes status UNCERTAIN; NEVER retry.
    fields = {
        "access_token": token, "title": before["title"],
        "content": json.dumps(after["content"], ensure_ascii=False, separators=(",", ":")),
        "author_name": before["author_name"], "author_url": before["author_url"],
        "return_content": "true",
    }
    if len(fields["content"].encode("utf-8")) > 64_000:
        raise UnsafeRevision("Telegraph content exceeds conservative byte limit; no POST")
    edited = post_form("editPage/" + path, fields)
    if edited.get("path") != path:
        raise UnsafeRevision("Provider effect UNCERTAIN: editPage changed path; do not retry")
    check = get_public_page(path)
    if check.get("path") != path or check.get("title") != before["title"] or check.get("author_name") != before["author_name"] or check.get("author_url") != before["author_url"]:
        raise UnsafeRevision("Provider effect UNCERTAIN: metadata drift, do not retry")
    if check.get("content") != after["content"]:
        raise UnsafeRevision("Provider effect UNCERTAIN: full content mismatch, do not retry")
    result["effect"] = "VERIFIED_IN_PLACE"
    result["verified_at_utc"] = datetime.now(timezone.utc).isoformat()
    receipt_file.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", choices=("03", "history-01", "both"), default="both")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--receipt-dir", type=Path)
    args = parser.parse_args()
    if args.execute and args.page == "both":
        parser.error("Each execution must target exactly one existing page")
    if args.execute and args.confirm != CONFIRM:
        parser.error("Execution requires --confirm " + CONFIRM)
    keys = ("03", "history-01") if args.page == "both" else (args.page,)
    for key in keys:
        try:
            outcome = run_one(key, execute=args.execute, confirm=args.confirm, receipt_dir=args.receipt_dir)
        except Exception as exc:
            # Never echo arbitrary provider errors (can contain credentials).
            print(f"{key}: STOP / no automatic retry ({type(exc).__name__})")
            raise SystemExit(2) from None
        print(json.dumps(outcome, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
