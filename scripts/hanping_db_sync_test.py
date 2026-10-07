from pathlib import Path
import json
import sqlite3

import scripts.hanping_db_sync as mod


def test_sync_creates_shared_schema(tmp_path: Path, monkeypatch):
    db_root = tmp_path / "db"
    monkeypatch.setattr(mod, "DB_PATH", db_root / "abel.sqlite3")
    monkeypatch.setattr(mod, "DEFAULT_INPUT", tmp_path / "normalized.json")

    payload = {
        "schema_version": 1,
        "source": "hanping",
        "words": [{
            "source": "hanping", "hanzi": "维护", "simplified": "维护",
            "traditional": "維護", "pinyin": "wei2 hu4", "starred": True,
            "tags": ["HSK6", "工作"], "note": "公司用语",
            "record_hash": "abc",
        }],
    }
    inp = tmp_path / "normalized.json"
    inp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    stats = mod.sync(inp)
    assert stats == {"inserted": 1, "updated": 0, "total": 1}

    with sqlite3.connect(mod.DB_PATH) as db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"wordbooks", "words", "wordbook_words", "abel_classifications",
                "hanping_vocab", "hanping_tags", "hanping_vocab_tags"} <= tables
        assert db.execute("SELECT word FROM words").fetchone()[0] == "维护"
        assert db.execute("SELECT starred FROM hanping_vocab").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM hanping_vocab_tags").fetchone()[0] == 2
