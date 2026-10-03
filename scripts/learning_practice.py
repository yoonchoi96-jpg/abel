#!/usr/bin/env python3
"""Deterministic Abel practice/session engine.

The engine handles delivery and scoring only. It does not invent questions,
answers, transcripts, or source material.
"""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone

SCHEMA="abel.learning.practice.v1"
KINDS={"listening","reading","writing","mock_test"}

def validate_unit(unit):
    required=("id","kind","language","level","questions")
    missing=[k for k in required if not unit.get(k)]
    if missing: raise ValueError("missing: "+",".join(missing))
    if unit["kind"] not in KINDS: raise ValueError("invalid kind")
    if not isinstance(unit["questions"],list) or not unit["questions"]:
        raise ValueError("questions must be non-empty")
    for q in unit["questions"]:
        if not q.get("id") or "answer" not in q:
            raise ValueError("each question needs id and answer")
    return True

def normalize_answer(value):
    if isinstance(value,list): return [normalize_answer(v) for v in value]
    return str(value).strip().casefold()

def score(unit, answers):
    validate_unit(unit)
    results=[]
    correct=0
    for q in unit["questions"]:
        expected=normalize_answer(q["answer"])
        actual=normalize_answer(answers.get(q["id"])) if q["id"] in answers else None
        ok=actual is not None and actual==expected
        correct += int(ok)
        results.append({"question_id":q["id"],"correct":ok,
                        "expected":q["answer"] if not ok else None,
                        "answer":answers.get(q["id"])})
    total=len(results)
    return {
        "schema_version":SCHEMA,"unit_id":unit["id"],"kind":unit["kind"],
        "language":unit["language"],"level":unit["level"],
        "total":total,"correct":correct,
        "score":round(correct/total*100,2) if total else 0,
        "results":results,"completed_at":datetime.now(timezone.utc).isoformat()
    }

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("unit"); p.add_argument("answers")
    a=p.parse_args()
    unit=json.load(open(a.unit,encoding="utf-8"))
    answers=json.load(open(a.answers,encoding="utf-8"))
    print(json.dumps(score(unit,answers),ensure_ascii=False,indent=2))
