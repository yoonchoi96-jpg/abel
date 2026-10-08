from pathlib import Path

from scripts.hanping_auto_sync import candidate_files


def test_candidate_files_finds_bounded_nested_hanping_exports(tmp_path: Path):
    root = tmp_path / "Downloads"
    direct = root / "Hanping"
    nested = direct / "exports" / "2026"
    deep = nested / "too" / "deep" / "folder"
    direct.mkdir(parents=True)
    nested.mkdir(parents=True)
    deep.mkdir(parents=True)

    (direct / "vocab.json").write_text("{}", encoding="utf-8")
    (nested / "backup.csv").write_text("word\n维护\n", encoding="utf-8")
    (deep / "ignored.json").write_text("{}", encoding="utf-8")
    (root / "unrelated.json").write_text("{}", encoding="utf-8")

    found = candidate_files([root], max_depth=3)

    assert direct / "vocab.json" in found
    assert nested / "backup.csv" in found
    assert deep / "ignored.json" not in found
    assert root / "unrelated.json" not in found


def test_file_hash_is_deterministic_for_stable_file(tmp_path: Path):
    from scripts.hanping_auto_sync import file_hash
    import hashlib

    path = tmp_path / "Hanping" / "vocab.json"
    path.parent.mkdir()
    path.write_text('{"words":[]}', encoding="utf-8")

    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    assert file_hash(path) == expected


def test_run_once_processes_only_newest_snapshot(tmp_path: Path, monkeypatch):
    from scripts import hanping_auto_sync as mod

    old = tmp_path / "Hanping" / "old.json"
    new = tmp_path / "Hanping" / "new.json"
    old.parent.mkdir(parents=True)
    old.write_text('{"words":[]}', encoding="utf-8")
    new.write_text('{"words":[]}', encoding="utf-8")

    old.touch()
    new.touch()
    old_mtime = old.stat().st_mtime_ns
    new_mtime = old_mtime + 1_000_000
    import os
    os.utime(new, ns=(new_mtime, new_mtime))

    calls = []
    monkeypatch.setattr(mod, "load_state", lambda: {})
    monkeypatch.setattr(mod, "file_hash", lambda path: path.name)
    monkeypatch.setattr(mod, "process", lambda path: calls.append(path) or {"route_counts": {}})
    monkeypatch.setattr(mod, "save_state", lambda state: None)

    assert mod.run_once([old.parent]) == 1
    assert calls == [new]
