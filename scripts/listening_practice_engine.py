#!/usr/bin/env python3
"""Abel source-backed listening practice engine.

Validates a listening resource's MP3/question/answer/transcript relationships,
scores submitted answers, and emits an error-analysis envelope. It never
creates missing source material.
"""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone

SCHEMA="abel.learning.listening.v1"

def validate_resource(resource):
    required=("id","language","level","audio","questions","answer_key")
    missing=[k for k in required if not resource.get(k)]
    if missing:
        raise ValueError("missing: "+",".join(missing))
    if not isinstance(resource["questions"],list) or not resource["questions"]:
        raise ValueError("questions must be non-empty")
    if not isinstance(resource["answer_key"],dict):
        raise ValueError("answer_key must be an object")
    qids={q.get("id") for q in resource["questions"]}
    if None in qids:
        raise ValueError("every question needs id")
    if qids != set(resource["answer_key"]):
        raise ValueError("question/answer-key mismatch")
    for q in resource["questions"]:
        if q.get("type") not in (None,"choice","short_answer","dictation"):
            raise ValueError("invalid question type")
    return True

def normalize(value):
    return str(value).strip().casefold()

def score(resource, answers):
    validate_resource(resource)
    rows=[]
    correct=0
    for q in resource["questions"]:
        qid=q["id"]
        expected=resource["answer_key"][qid]
        actual=answers.get(qid)
        ok=actual is not None and normalize(actual)==normalize(expected)
        correct += int(ok)
        rows.append({
            "question_id":qid,
            "correct":ok,
            "answer":actual,
            "expected":None if ok else expected,
            "error_type":None if ok else q.get("error_type","listening_comprehension")
        })
    total=len(rows)
    return {
        "schema_version":SCHEMA,
        "resource_id":resource["id"],
        "language":resource["language"],
        "level":resource["level"],
        "audio":resource["audio"],
        "transcript":resource.get("transcript"),
        "total":total,
        "correct":correct,
        "score":round(correct/total*100,2) if total else 0,
        "results":rows,
        "source":resource.get("source"),
        "source_links":resource.get("source_links",[]),
        "completed_at":datetime.now(timezone.utc).isoformat()
    }

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("resource")
    p.add_argument("answers")
    p.add_argument("--out",required=True)
    a=p.parse_args()
    resource=json.load(open(a.resource,encoding="utf-8"))
    answers=json.load(open(a.answers,encoding="utf-8"))
    out=score(resource,answers)
    json.dump(out,open(a.out,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
    print(a.out)
