#!/usr/bin/env python3
"""Abel deterministic mock-test integrity and scoring engine.

A mock test is a source-backed composition of existing practice units.
This module validates references, preserves source metadata, and aggregates
scores. It never invents questions, answers, or source material.
"""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone

SCHEMA="abel.learning.mock-test.v1"
KINDS=("listening","reading","writing")

def validate_mock(mock, units):
    required=("id","language","level","exam_system","sections")
    missing=[k for k in required if not mock.get(k)]
    if missing:
        raise ValueError("missing: "+",".join(missing))
    if not isinstance(mock["sections"],list) or not mock["sections"]:
        raise ValueError("sections must be non-empty")
    by_id={u.get("id"):u for u in units}
    seen=set()
    for section in mock["sections"]:
        if section.get("kind") not in KINDS:
            raise ValueError("invalid section kind")
        unit_id=section.get("unit_id")
        if not unit_id or unit_id not in by_id:
            raise ValueError("unknown unit_id: "+str(unit_id))
        if unit_id in seen:
            raise ValueError("duplicate unit_id: "+unit_id)
        seen.add(unit_id)
        unit=by_id[unit_id]
        if unit.get("language")!=mock["language"] or unit.get("level")!=mock["level"]:
            raise ValueError("unit metadata mismatch: "+unit_id)
        if unit.get("kind")!=section["kind"]:
            raise ValueError("unit kind mismatch: "+unit_id)
    return True

def aggregate(mock, units, results):
    validate_mock(mock, units)
    result_by_unit={r.get("unit_id"):r for r in results}
    sections=[]
    total=correct=0
    for section in mock["sections"]:
        uid=section["unit_id"]
        result=result_by_unit.get(uid)
        if not result:
            sections.append({"kind":section["kind"],"unit_id":uid,"status":"not_attempted"})
            continue
        if result.get("kind")!=section["kind"]:
            raise ValueError("result kind mismatch: "+uid)
        t=int(result.get("total",0)); c=int(result.get("correct",0))
        total+=t; correct+=c
        sections.append({
            "kind":section["kind"],"unit_id":uid,"status":"completed",
            "total":t,"correct":c,"score":result.get("score")
        })
    return {
        "schema_version":SCHEMA,
        "mock_test_id":mock["id"],
        "language":mock["language"],
        "level":mock["level"],
        "exam_system":mock["exam_system"],
        "source":mock.get("source"),
        "source_links":mock.get("source_links",[]),
        "total":total,"correct":correct,
        "score":round(correct/total*100,2) if total else 0,
        "sections":sections,
        "completed_at":datetime.now(timezone.utc).isoformat(),
    }

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("mock")
    p.add_argument("units")
    p.add_argument("results")
    p.add_argument("--out",required=True)
    a=p.parse_args()
    mock=json.load(open(a.mock,encoding="utf-8"))
    units=json.load(open(a.units,encoding="utf-8"))
    results=json.load(open(a.results,encoding="utf-8"))
    if isinstance(units,dict): units=units.get("units",[])
    if isinstance(results,dict): results=results.get("results",[])
    out=aggregate(mock,units,results)
    json.dump(out,open(a.out,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
    print(a.out)
