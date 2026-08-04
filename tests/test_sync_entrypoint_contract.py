from __future__ import annotations

import argparse
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import sync_youtube_to_vk as sync
from scripts import sync_youtube_to_vk_textsafe as textsafe
from video_channel_manager.domain.enums import PlatformName

ROOT = Path(__file__).resolve().parents[1]


def _runtime(*, source_channel_id: str = "UC-78ys2S3cQ3lpqgXfo-SvQ") -> sync.SyncRuntime:
    return sync.SyncRuntime(
        project_key="legendary-poet",
        expected_source_channel_id=source_channel_id,
        expected_community_id=235216998,
        render_title=lambda value: value,
        render_description=lambda value: value,
        download_media=lambda **kwargs: Path(str(kwargs["cache_dir"])) / "media.mp4",
    )


def test_direct_base_main_fails_before_configuration_or_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden() -> object:
        raise AssertionError("base main touched configuration before rejecting direct execution")

    monkeypatch.setattr(sync, "get_settings", forbidden)

    with pytest.raises(SystemExit, match="internal engine"):
        sync.main([])


def test_base_run_rejects_wrong_source_channel_before_token_access(monkeypatch: pytest.MonkeyPatch) -> None:
    source = SimpleNamespace(
        channel=SimpleNamespace(
            ref=SimpleNamespace(
                platform=PlatformName.YOUTUBE,
                channel_id="UCeSJsC6go2c9pdJCuUI1BYA",
            )
        )
    )
    monkeypatch.setattr(sync, "get_settings", lambda: object())
    monkeypatch.setattr(sync, "load_audit", lambda path: source)

    class ForbiddenTokenStore:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise AssertionError("token store opened before source identity check")

    monkeypatch.setattr(sync, "VkTokenStore", ForbiddenTokenStore)
    args = argparse.Namespace(write_delay=0.0, source=Path("source.json"))

    with pytest.raises(SystemExit, match="does not match runtime project"):
        sync.run(args, runtime=_runtime())


def test_supported_entrypoint_rejects_cross_project_pair_before_render_or_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = SimpleNamespace(channel=SimpleNamespace(ref=SimpleNamespace(channel_id="UC-78ys2S3cQ3lpqgXfo-SvQ")))
    community = SimpleNamespace(ref=SimpleNamespace(channel_id="60805374"))
    monkeypatch.setattr(
        textsafe,
        "get_settings",
        lambda: SimpleNamespace(data_dir=tmp_path, vk_api_version="5.199"),
    )
    monkeypatch.setattr(textsafe, "VkTokenStore", lambda _data_dir: object())

    class FakeReader:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def get_community(self, _community: str) -> object:
            return community

    monkeypatch.setattr(textsafe, "VkApiClient", FakeReader)
    monkeypatch.setattr(textsafe.sync, "load_audit", lambda _path: source)
    monkeypatch.setattr(
        textsafe,
        "_render_title",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("renderer called")),
    )
    args = argparse.Namespace(
        account="legendary-poet",
        community="60805374",
        source=Path("source.json"),
    )

    with pytest.raises(ValueError, match="do not resolve to one registered project"):
        textsafe._provider_identity(args)


def test_supported_entrypoint_uses_explicit_runtime_not_global_monkeypatch() -> None:
    path = ROOT / "scripts" / "sync_youtube_to_vk_textsafe.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    sync_attribute_writes: list[str] = []
    runtime_calls = 0
    run_calls = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "sync"
                ):
                    sync_attribute_writes.append(target.attr)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "sync":
                if node.func.attr == "SyncRuntime":
                    runtime_calls += 1
                if node.func.attr == "run":
                    run_calls += 1

    assert sync_attribute_writes == []
    assert runtime_calls == 1
    assert run_calls == 1
