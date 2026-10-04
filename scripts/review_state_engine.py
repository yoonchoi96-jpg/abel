#!/usr/bin/env python3
"""Deterministic spaced-review state for Abel."""
from __future__ import annotations
import argparse, json, sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA="abel.learning.review-state.v1"

def connect(path):
    con=sqlite3.connect(path); con.row_factory=sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS review_states(
      language TEXT NOT NULL, question_id TEXT NOT NULL, resource_id TEXT NOT NULL,
      kind TEXT, level TEXT, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
      review_count INTEGER NOT NULL DEFAULT 0, correct_count INTEGER NOT NULL DEFAULT 0,
      wrong_count INTEGER NOT NULL DEFAULT 0, consecutive_correct INTEGER NOT NULL DEFAULT 0,
      consecutive_wrong INTEGER NOT NULL DEFAULT 0, last_result TEXT,
      interval_days REAL NOT NULL DEFAULT 0, next_review_at TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'active', updated_at TEXT NOT NULL,
      PRIMARY KEY(language,question_id,resource_id))""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_review_due ON review_states(language,next_review_at,status)")
    con.commit(); return con

def _now(): return datetime.now(timezone.utc)
def _iso(dt): return dt.isoformat()
def _parse(s): return datetime.fromisoformat(s.replace("Z","+00:00"))

def apply_result(language, question_id, resource_id, correct, *, kind=None, level=None, at=None, db_path="data/abel_learning.db", connection=None):
    if not language or not question_id or not resource_id: raise ValueError("language, question_id, resource_id required")
    at=_parse(at) if at else _now(); now=_iso(at)
    own_connection = connection is None
    con = connection if connection is not None else connect(db_path)
    row=con.execute("SELECT * FROM review_states WHERE language=? AND question_id=? AND resource_id=?",(language,question_id,resource_id)).fetchone()
    if row is None:
        interval=1.0 if correct else 0.0
        next_at=at+timedelta(days=interval)
        con.execute("""INSERT INTO review_states(language,question_id,resource_id,kind,level,first_seen,last_seen,review_count,correct_count,wrong_count,consecutive_correct,consecutive_wrong,last_result,interval_days,next_review_at,status,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(language,question_id,resource_id,kind,level,now,now,1,int(correct),int(not correct),int(correct),int(not correct),"correct" if correct else "wrong",interval,_iso(next_at),"active",now))
    else:
        cc=int(row["consecutive_correct"]); cw=int(row["consecutive_wrong"]); interval=float(row["interval_days"])
        if correct:
            cc+=1; cw=0
            interval={0:2.0,1:2.0,2:4.0,3:7.0}.get(cc-1,min(30.0,max(1.0,interval*2.0)))
        else:
            cw+=1; cc=0; interval=0.0
        next_at=at+timedelta(days=interval)
        status="mastered" if cc>=5 else "active"
        con.execute("""UPDATE review_states SET kind=COALESCE(?,kind),level=COALESCE(?,level),last_seen=?,review_count=review_count+1,correct_count=correct_count+?,wrong_count=wrong_count+?,consecutive_correct=?,consecutive_wrong=?,last_result=?,interval_days=?,next_review_at=?,status=?,updated_at=? WHERE language=? AND question_id=? AND resource_id=?""",
        (kind,level,now,int(correct),int(not correct),cc,cw,"correct" if correct else "wrong",interval,_iso(next_at),status,now,language,question_id,resource_id))
    if own_connection:
        con.commit()
    out=dict(con.execute("SELECT * FROM review_states WHERE language=? AND question_id=? AND resource_id=?",(language,question_id,resource_id)).fetchone())
    if own_connection:
        con.close()
    return out

def due_items(language, db_path="data/abel_learning.db", limit=20, now=None):
    if limit<1 or limit>100: raise ValueError("limit must be 1..100")
    now=_parse(now) if now else _now(); con=connect(db_path)
    rows=con.execute("""SELECT * FROM review_states WHERE language=? AND status='active' AND next_review_at<=? ORDER BY next_review_at ASC, wrong_count DESC, question_id ASC LIMIT ?""",(language,_iso(now),limit)).fetchall()
    con.close(); return [dict(r) for r in rows]

def main():
    p=argparse.ArgumentParser(); p.add_argument("--db",default="data/abel_learning.db"); p.add_argument("--language"); p.add_argument("--question-id"); p.add_argument("--resource-id"); p.add_argument("--correct",action="store_true"); p.add_argument("--wrong",action="store_true"); p.add_argument("--at"); p.add_argument("--out")
    a=p.parse_args()
    if a.correct==a.wrong: raise SystemExit("choose exactly one of --correct/--wrong")
    if not a.language or not a.question_id or not a.resource_id: raise SystemExit("language/question/resource required")
    result=apply_result(a.language,a.question_id,a.resource_id,a.correct,at=a.at,db_path=a.db)
    if a.out: Path(a.out).write_text(json.dumps({"schema_version":SCHEMA,"state":result},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    else: print(json.dumps({"schema_version":SCHEMA,"state":result},ensure_ascii=False,indent=2))
if __name__=="__main__": main()
