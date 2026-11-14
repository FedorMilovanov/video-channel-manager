"""Offline regression tests: never alter originals; hash duplicate vs distinct versions."""
import importlib.util
import pathlib

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "collect_legendary_poet_audio.py"
spec = importlib.util.spec_from_file_location("tlp_audio_collector", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def test_audio_collection_is_idempotent_and_preserves_alternate_versions(tmp_path):
    source_a = tmp_path / "Downloads"
    source_b = tmp_path / "Project"
    target = tmp_path / "Легендарный поэт" / "_АУДИО_НА_ПРОСЛУШИВАНИЕ"
    source_a.mkdir()
    source_b.mkdir()
    (source_a / "Ночь.mp3").write_bytes(b"version one")
    (source_a / "Same recording.mp3").write_bytes(b"version one")
    (source_b / "Ночь.mp3").write_bytes(b"version TWO")
    (source_b / "Mix.wav").write_bytes(b"lossless song")
    (source_b / "End card.mp4").write_bytes(b"not an audio file")
    dry = module.collect([source_a, source_b], target, False, {".mp3", ".wav"})
    assert (dry["file_count"], dry["unique_count"], dry["copied_count"]) == (4, 3, 0)
    assert list(target.glob("*.mp3")) == []
    after = module.collect([source_a, source_b], target, True, {".mp3", ".wav"})
    assert (after["file_count"], after["exact_duplicates"], after["copied_count"]) == (4, 1, 3)
    assert len(list(target.glob("*.mp3"))) == 2
    assert len(list(target.glob("*.wav"))) == 1
    assert len((target / "_ВСЕ_НА_ПРОСЛУШИВАНИЕ.m3u8").read_text(encoding="utf-8-sig").splitlines()) == 4
    again = module.collect([source_a, source_b], target, True, {".mp3", ".wav"})
    assert again["copied_count"] == 0
    assert (source_a / "Ночь.mp3").read_bytes() == b"version one"
    assert (source_b / "Ночь.mp3").read_bytes() == b"version TWO"
    assert (source_b / "End card.mp4").exists()

def test_target_excluded_from_recursive_rescan(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "song.wav").write_bytes(b"wav")
    target = root / "Легендарный поэт" / "_АУДИО_НА_ПРОСЛУШИВАНИЕ"
    first = module.collect([root], target, True, {".wav"})
    second = module.collect([root], target, True, {".wav"})
    assert first["file_count"] == second["file_count"] == 1
    assert second["copied_count"] == 0
