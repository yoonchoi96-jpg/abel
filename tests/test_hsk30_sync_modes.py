import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import hsk30_sync as h  # noqa: E402


def test_status_is_read_only_and_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(h, "DB_PATH", tmp_path / "missing.sqlite3")
    result = h.status()
    assert json.loads(capsys.readouterr().out) == result
    assert result["hsk30:7-9"]["status"] == "INCOMPLETE"
    assert not (tmp_path / "missing.sqlite3").exists()


def test_validate_detects_known_issues(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(h, "DB_PATH", tmp_path / "missing.sqlite3")
    result = h.validate()
    capsys.readouterr()
    codes = {(i["code"], i["curriculum"]) for i in result["issues"]}
    assert ("MISSING_TRADITIONAL", "hsk30:7-9") in codes
    assert ("EMPTY_KOREAN_GLOSS", "hsk30:7-9") in codes
    assert result["summary"]["errors"] >= 1


def test_dry_run_changes_nothing(tmp_path, monkeypatch, capsys):
    db = tmp_path / "x.sqlite3"
    monkeypatch.setattr(h, "DB_PATH", db)
    export_before = h.EXPORT.read_bytes()
    result = h.dry_run()
    capsys.readouterr()
    assert result["mode"] == "dry-run"
    assert result["estimate"]["csv_files_read"] == 2
    assert not db.exists()
    assert h.EXPORT.read_bytes() == export_before
