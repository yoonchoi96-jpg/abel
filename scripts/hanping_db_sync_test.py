from pathlib import Path
import json
import sqlite3

import scripts.hanping_db_sync as mod


def _write_payload(path: Path, *, starred: bool, note, tags, record_hash: str):
    payload = {
        "schema_version": 1,
        "source": "hanping",
        "words": [{
            "source": "hanping",
            "hanzi": "维护",
            "simplified": "维护",
            "traditional": "維護",
            "pinyin": "wei2 hu4",
            "starred": starred,
            "tags": tags,
            "note": note,
            "record_hash": record_hash,
        }],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_sync_creates_shared_schema(tmp_path: Path, monkeypatch):
    db_root = tmp_path / "db"
    monkeypatch.setattr(mod, "DB_PATH", db_root / "abel.sqlite3")
    monkeypatch.setattr(mod, "DEFAULT_INPUT", tmp_path / "normalized.json")

    inp = tmp_path / "normalized.json"
    _write_payload(
        inp,
        starred=True,
        note="公司用语",
        tags=["HSK6", "工作"],
        record_hash="abc",
    )

    stats = mod.sync(inp)
    assert stats == {"inserted": 1, "updated": 0, "total": 1}

    with sqlite3.connect(mod.DB_PATH) as db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"wordbooks", "words", "wordbook_words", "abel_classifications",
                "hanping_vocab", "hanping_tags", "hanping_vocab_tags"} <= tables
        assert db.execute("SELECT word FROM words").fetchone()[0] == "维护"
        assert db.execute("SELECT starred FROM hanping_vocab").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM hanping_vocab_tags").fetchone()[0] == 2


def test_sync_is_idempotent_and_snapshot_authoritative(tmp_path: Path, monkeypatch):
    db_root = tmp_path / "db"
    monkeypatch.setattr(mod, "DB_PATH", db_root / "abel.sqlite3")

    inp = tmp_path / "normalized.json"
    _write_payload(
        inp,
        starred=True,
        note="첫 메모",
        tags=["HSK6", "업무"],
        record_hash="first",
    )
    assert mod.sync(inp) == {"inserted": 1, "updated": 0, "total": 1}
    assert mod.sync(inp) == {"inserted": 0, "updated": 1, "total": 1}

    _write_payload(
        inp,
        starred=False,
        note=None,
        tags=["복습"],
        record_hash="second",
    )
    assert mod.sync(inp) == {"inserted": 0, "updated": 1, "total": 1}

    with sqlite3.connect(mod.DB_PATH) as db:
        assert db.execute("SELECT COUNT(*) FROM words").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM wordbooks").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM wordbook_words").fetchone()[0] == 1
        assert db.execute("SELECT starred, note, record_hash FROM hanping_vocab").fetchone() == (
            0, None, "second"
        )
        assert db.execute(
            """SELECT t.name
               FROM hanping_vocab_tags vt
               JOIN hanping_tags t ON t.id=vt.tag_id
               ORDER BY t.name"""
        ).fetchall() == [("복습",)]


def test_sync_reuses_existing_hsk_word_when_word_and_pinyin_match(tmp_path: Path, monkeypatch):
    db_root = tmp_path / "db"
    monkeypatch.setattr(mod, "DB_PATH", db_root / "abel.sqlite3")

    mod.init_db()
    with sqlite3.connect(mod.DB_PATH) as db:
        db.execute(
            """INSERT INTO words(
                   word, meaning, pronunciation, part_of_speech, example,
                   source_url, first_seen, last_seen, raw_json
               ) VALUES(?,?,?,?,?,?,?,?,?)""",
            ("维护", "유지하다", "wei2 hu4", "동사", "", "hsk30_level6_1140.csv",
             "2026-10-07T00:00:00+00:00", "2026-10-07T00:00:00+00:00", "{}"),
        )
        db.commit()

    inp = tmp_path / "normalized.json"
    _write_payload(
        inp,
        starred=True,
        note="HSK 복습",
        tags=["HSK6"],
        record_hash="hsk-match",
    )

    assert mod.sync(inp) == {"inserted": 0, "updated": 1, "total": 1}

    with sqlite3.connect(mod.DB_PATH) as db:
        assert db.execute("SELECT COUNT(*) FROM words").fetchone()[0] == 1
        assert db.execute("SELECT meaning FROM words").fetchone()[0] == "유지하다"
        assert db.execute("SELECT word_id FROM hanping_vocab").fetchone()[0] == 1
