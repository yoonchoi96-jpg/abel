#!/usr/bin/env python3
"""Durable-friendly learning session event model for Abel."""
from __future__ import annotations
import argparse, json, sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB = Path("data/abel_learning.db")
SCHEMA_VERSION = 3

def connect(path=DB):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path); con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""CREATE TABLE IF NOT EXISTS learning_sessions(
      id INTEGER PRIMARY KEY AUTOINCREMENT, language TEXT NOT NULL, session_type TEXT NOT NULL,
      resource_id TEXT, level TEXT, started_at TEXT NOT NULL, duration_seconds INTEGER,
      score REAL, total INTEGER, correct INTEGER, payload_json TEXT NOT NULL,
      created_at TEXT NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS practice_errors(
      id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL,
      language TEXT NOT NULL, question_id TEXT NOT NULL, resource_id TEXT,
      kind TEXT, level TEXT, error_type TEXT, occurred_at TEXT NOT NULL,
      FOREIGN KEY(session_id) REFERENCES learning_sessions(id))""")
    con.execute("""CREATE TABLE IF NOT EXISTS provider_learning_events( id INTEGER PRIMARY KEY AUTOINCREMENT, language TEXT NOT NULL, task_type TEXT NOT NULL, model TEXT, cache_key TEXT, input_summary TEXT, output_json TEXT NOT NULL, created_at TEXT NOT NULL)""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_provider_events_lang_time ON provider_learning_events(language, created_at)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_provider_events_task ON provider_learning_events(language, task_type)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_learning_sessions_lang_time ON learning_sessions(language, started_at)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_practice_errors_lang_type ON practice_errors(language, error_type)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_practice_errors_lang_question ON practice_errors(language, question_id)")
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
    session_id=cur.lastrowid
    payload=session.get("payload",{})
    for row in payload.get("results",[]) if isinstance(payload,dict) else []:
        if row.get("correct") is True:
            continue
        qid=str(row.get("question_id","")).strip()
        if not qid:
            continue
        con.execute("""INSERT INTO practice_errors
          (session_id,language,question_id,resource_id,kind,level,error_type,occurred_at)
          VALUES(?,?,?,?,?,?,?,?)""",(
          session_id,session["language"],qid,session.get("resource_id"),
          session.get("session_type"),session.get("level"),row.get("error_type"),now))
    con.commit(); con.close(); return session_id

def record_provider_event(language: str, task_type: str, output: dict, *, model=None, cache_key=None, input_summary="", db_path=DB):
    if not language or not task_type:
        raise ValueError("language and task_type are required")
    now=datetime.now(timezone.utc).isoformat()
    con=connect(db_path)
    cur=con.execute("""INSERT INTO provider_learning_events
      (language,task_type,model,cache_key,input_summary,output_json,created_at)
      VALUES(?,?,?,?,?,?,?)""",(
      language,task_type,model,cache_key,input_summary,json.dumps(output,ensure_ascii=False),now))
    con.commit(); con.close(); return cur.lastrowid

def provider_recent(language, db_path=DB, limit=20):
    con=connect(db_path)
    rows=con.execute("""SELECT task_type,model,cache_key,input_summary,output_json,created_at FROM provider_learning_events WHERE language=? ORDER BY id DESC LIMIT ?""",(language,limit)).fetchall()
    con.close()
    out=[]
    for r in rows:
        x=dict(r)
        try: x["output"]=json.loads(x.pop("output_json"))
        except Exception: x["output"]=x.pop("output_json")
        out.append(x)
    return out

def provider_summary(language, db_path=DB):
    con=connect(db_path)
    rows=con.execute("""SELECT task_type,COUNT(*) count,MAX(created_at) last_created_at
      FROM provider_learning_events WHERE language=? GROUP BY task_type
      ORDER BY count DESC,task_type""",(language,)).fetchall()
    con.close()
    return {"schema_version":"abel.learning.provider-summary.v1","language":language,"events":[dict(r) for r in rows]}

def summary(language, db_path=DB):
    con=connect(db_path)
    rows=con.execute("""SELECT session_type,COUNT(*) n,AVG(score) avg_score,
      SUM(duration_seconds) seconds FROM learning_sessions WHERE language=? GROUP BY session_type""",(language,)).fetchall()
    errors=con.execute("""SELECT error_type,COUNT(*) count,COUNT(DISTINCT question_id) questions
      FROM practice_errors WHERE language=? GROUP BY error_type ORDER BY count DESC,error_type""",(language,)).fetchall()
    con.close()
    return {
      "schema_version":"abel.learning.session-summary.v2",
      "language":language,
      "session_types":[dict(r) for r in rows],
      "practice_errors":[dict(r) for r in errors],
    }

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--language",required=True); p.add_argument("--summary",action="store_true")
    a=p.parse_args()
    print(json.dumps(summary(a.language) if a.summary else {"status":"use as library"},ensure_ascii=False,indent=2))
