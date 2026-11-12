"""Provider-inert contract for the independent four-photo Meta readback."""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/instagram/lord_god_quote_receipt_readonly_20261112.py"


@pytest.fixture
def reader(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("readonly_quote_receipt", SCRIPT)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    plan = {
        "project": "lord-god-strength",
        "account_id": m.ACCOUNT,
        "page_id": m.PAGE,
        "tz": "Europe/Moscow",
        "items": [
            {"id": ident, "date": day, "time": "12:45", "caption": f"Offline approved {ident}"}
            for ident, day in m.EXPECTED
        ],
    }
    p = tmp_path / "plan.json"
    p.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf8")
    monkeypatch.setattr(m, "PLAN", p)
    monkeypatch.setattr(m, "PLAN_SHA256", hashlib.sha256(p.read_bytes()).hexdigest())
    return m


def _image(item):
    return {
        "id": "123456789",
        "caption": item["caption"],
        "media_type": "IMAGE",
        "permalink": "https://www.instagram.com/p/offline-test/",
        "timestamp": "2026-11-12T09:45:05+00:00",
    }


def test_immutable_plan_rejects_caption_tampering(reader):
    assert len(reader.read_plan()) == 4
    reader.PLAN.write_bytes(reader.PLAN.read_bytes() + b" ")
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        reader.read_plan()


@pytest.mark.parametrize(
    "paging",
    [None, False, [], "", {"next": ""}, {"next": None}, {"next": "https://untrusted.example/", "cursors": None}],
)
def test_malformed_paging_fails_closed(reader, monkeypatch, paging):
    monkeypatch.setattr(reader, "graph_get", lambda *args, **kwargs: {"data": [], "paging": paging})
    with pytest.raises(RuntimeError, match="malformed|incomplete"):
        reader.list_media("offline-token")


def test_paging_never_dereferences_untrusted_next(reader, monkeypatch):
    calls = []

    def fake(token, path, params=None):
        calls.append((path, params))
        if len(calls) == 1:
            return {
                "data": [{"id": "111"}],
                "paging": {"next": "https://untrusted.example/exfiltrate", "cursors": {"after": "opaque/+="}},
            }
        return {"data": [{"id": "222"}]}

    monkeypatch.setattr(reader, "graph_get", fake)
    assert len(reader.list_media("fake-token")) == 2
    assert len(calls) == 2
    assert calls[1][0] == reader.ACCOUNT + "/media"
    assert calls[1][1]["after"] == "opaque/+="


def test_duplicate_photo_caption_fails_closed(reader):
    row = reader.read_plan()[0]
    with pytest.raises(RuntimeError, match="Duplicate"):
        reader.exact_receipt(row, [_image(row), dict(_image(row), id="234567891")])


@pytest.mark.parametrize(
    "field,value",
    [
        ("media_type", "VIDEO"),
        ("permalink", "https://attacker.example/p/test"),
        ("permalink", "http://www.instagram.com/p/test"),
        ("timestamp", "2026-11-13T09:45:00Z"),
        ("timestamp", "invalid-timestamp"),
        ("id", "abc"),
    ],
)
def test_invalid_provider_photo_evidence_is_not_proven(reader, field, value):
    row = reader.read_plan()[0]
    post = _image(row)
    post[field] = value
    with pytest.raises(RuntimeError, match="not proven|Invalid IMAGE"):
        reader.exact_receipt(row, [post])


def test_valid_image_receipt(reader):
    row = reader.read_plan()[0]
    assert reader.exact_receipt(row, [_image(row)])["id"] == "123456789"


def test_missing_receipt_is_not_found(reader):
    assert reader.exact_receipt(reader.read_plan()[0], []) is None


def test_graph_wire_is_get_only_and_token_not_in_url(reader, monkeypatch):
    calls = []

    class Response:
        def read(self, *args):
            return b'{"data": []}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout):
        calls.append((request.get_method(), request.full_url, request.get_header("Authorization")))
        return Response()

    monkeypatch.setattr(reader, "urlopen", fake_urlopen)
    assert reader.graph_get("offline-token", "me") == {"data": []}
    assert calls[0][0] == "GET"
    assert calls[0][1].startswith("https://graph.facebook.com/")
    assert "offline-token" not in calls[0][1]


def test_scheduled_missing_receipt_returns_nonzero(reader, monkeypatch):
    class Clock(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 12, 13, 40, tzinfo=tz)

    monkeypatch.setattr(reader, "dt", SimpleNamespace(datetime=Clock, time=dt.time))
    monkeypatch.setenv("LORD_GOD_QUOTE_RECEIPT_MODE", "scheduled")
    monkeypatch.setenv("LORD_GOD_PAGE_TOKEN", "X" * 40)
    monkeypatch.setattr(reader, "verify_identity", lambda token: None)
    monkeypatch.setattr(reader, "list_media", lambda token: [])
    assert reader.main() == 2


def test_preflight_is_provider_inert(reader, monkeypatch, capsys):
    monkeypatch.setenv("LORD_GOD_QUOTE_RECEIPT_MODE", "preflight")
    monkeypatch.setenv("LORD_GOD_PAGE_TOKEN", "X" * 40)
    monkeypatch.setattr(reader, "verify_identity", lambda token: None)
    monkeypatch.setattr(reader, "list_media", lambda token: [])
    assert reader.main() == 0
    assert "QUOTE_READBACK_PREFLIGHT_OK_NO_POST" in capsys.readouterr().out
