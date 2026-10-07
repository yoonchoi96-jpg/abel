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
