from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from daily_learning_queue import build_queue, SCHEMA


def test_queue_is_source_backed_and_deterministic(tmp_path):
    db = tmp_path / "learning.db"
    con = sqlite3.connect(db)
    con.executescript("""
    CREATE TABLE practice_errors(
      id INTEGER PRIMARY KEY, session_id INTEGER, language TEXT,
      question_id TEXT, resource_id TEXT, kind TEXT, level TEXT,
      error_type TEXT, occurred_at TEXT
    );
    """)
    rows = [
      ("zh-CN","q2","r2","reading","HSK6","grammar","2026-10-03T00:00:00+00:00"),
      ("zh-CN","q2","r2","reading","HSK6","grammar","2026-10-02T00:00:00+00:00"),
      ("zh-CN","q1","r1","listening","HSK6","word_choice","2026-10-03T00:00:00+00:00"),
      ("fr-FR","q9","r9","writing","B2","grammar","2026-10-03T00:00:00+00:00"),
    ]
    con.executemany(
      "INSERT INTO practice_errors(language,question_id,resource_id,kind,level,error_type,occurred_at) VALUES(?,?,?,?,?,?,?)",
      rows
    )
    con.commit(); con.close()

    a = build_queue("zh-CN", db, limit=10, days=30)
    b = build_queue("zh-CN", db, limit=10, days=30)

    assert a["schema_version"] == SCHEMA
    assert a["source_of_truth"] == "Abel"
    assert a["api_calls"] == 0
    assert a["rules"]["source_backed_only"] is True
    assert a["item_count"] == 2
    assert a["items"] == b["items"]
    assert a["items"][0]["question_id"] == "q2"
    assert a["items"][0]["wrong_count"] == 2
    assert all(x["language"] if "language" in x else True for x in a["items"])


def test_queue_excludes_missing_resource(tmp_path):
    db = tmp_path / "learning.db"
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE practice_errors(
      id INTEGER PRIMARY KEY, session_id INTEGER, language TEXT,
      question_id TEXT, resource_id TEXT, kind TEXT, level TEXT,
      error_type TEXT, occurred_at TEXT)""")
    con.execute(
      "INSERT INTO practice_errors(language,question_id,resource_id,kind,occurred_at) VALUES(?,?,?,?,?)",
      ("zh-CN","q1",None,"reading","2026-10-03T00:00:00+00:00")
    )
    con.commit(); con.close()
    out = build_queue("zh-CN", db)
    assert out["item_count"] == 0
