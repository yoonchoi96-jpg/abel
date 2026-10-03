#!/usr/bin/env python3
"""Durable-friendly learning session event model for Abel."""
from __future__ import annotations
import argparse, json, sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB = Path("data/abel_learning.db")
SCHEMA_VERSION = 1

def connect(path=DB):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path); con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""CREATE TABLE IF NOT EXISTS learning_sessions(
      id INTEGER PRIMARY KEY AUTOINCREMENT, language TEXT NOT NULL, session_type TEXT NOT NULL,
      resource_id TEXT, level TEXT, started_at TEXT NOT NULL, duration_seconds INTEGER,
      score REAL, total INTEGER, correct INTEGER, payload_json TEXT NOT NULL,
      created_at TEXT NOT NULL)""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_learning_sessions_lang_time ON learning_sessions(language, started_at)")
    con.commit(); return con

def record_session(session: dict, db_path=DB):
    required=("language","session_type")
    missing=[x for x in required if not session.get(x)]
    if missing: raise ValueError("missing: "+",".join(missing))
    now=datetime.now(timezone.utc).isoformat()
    con=connect(db_path)
    cur=con.execute("""INSERT INTO learning_sessions
      (language,session_type,resource_id,level,started_at,duration_seconds,score,total,correct,payload_json,created_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?)""",(
      session["language"],session["session_type"],session.get("resource_id"),session.get("level"),
      session.get("started_at",now),session.get("duration_seconds"),session.get("score"),
      session.get("total"),session.get("correct"),json.dumps(session,ensure_ascii=False),now))
    con.commit(); rid=cur.lastrowid; con.close(); return rid

def summary(language, db_path=DB):
    con=connect(db_path)
    rows=con.execute("""SELECT session_type,COUNT(*) n,AVG(score) avg_score,
      SUM(duration_seconds) seconds FROM learning_sessions WHERE language=? GROUP BY session_type""",(language,)).fetchall()
    con.close()
    return {"schema_version":"abel.learning.session-summary.v1","language":language,
            "session_types":[dict(r) for r in rows]}

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--language",required=True); p.add_argument("--summary",action="store_true")
    a=p.parse_args()
    print(json.dumps(summary(a.language) if a.summary else {"status":"use as library"},ensure_ascii=False,indent=2))
