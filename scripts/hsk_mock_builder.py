#!/usr/bin/env python3
"""Build source-backed HSK mock definitions from existing learning units.

The builder never creates questions, answers, audio, passages, or writing
prompts. It only binds already indexed units to an official exam profile.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from mock_test_engine import validate_mock

SUPPORTED_KINDS=("listening","reading","writing","translation","speaking")

def load_profiles(path):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version")!="abel.hsk.exam-profiles.v1":
        raise ValueError("invalid HSK profile schema")
    return data.get("profiles",{})

def build(profile_id, units, profiles, *, mock_id, source=None, source_links=None):
    if profile_id not in profiles:
        raise ValueError("unknown profile: "+profile_id)
    profile=profiles[profile_id]
    by_kind={}
    for unit in units:
        if unit.get("language")!="zh-CN":
            continue
        if unit.get("level")!=profile["level"]:
            continue
        by_kind.setdefault(unit.get("kind"),[]).append(unit)
    sections=[]
    for spec in profile["sections"]:
        kind=spec["kind"]
        if kind not in by_kind or not by_kind[kind]:
            raise ValueError(f"missing source-backed unit for section: {kind}")
        unit=sorted(by_kind[kind],key=lambda x:str(x.get("id","")))[0]
        sections.append({
            "kind":kind,
            "unit_id":unit["id"],
            "expected_items":spec["items"],
            "score_max":spec["score_max"]
        })
    mock={
        "id":mock_id,
        "language":"zh-CN",
        "level":profile["level"],
        "exam_system":profile["exam_system"],
        "profile_id":profile_id,
        "sections":sections,
        "source":source or "source-backed HSK exam profile",
        "source_links":source_links or []
    }
    if profile["level"] in ("HSK5","HSK6"):
        validate_mock(
            {**mock,"sections":[{"kind":x["kind"],"unit_id":x["unit_id"]} for x in sections]},
            units
        )
    return mock

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("profile")
    p.add_argument("units")
    p.add_argument("--profiles",default="data/hsk_exam_profiles.json")
    p.add_argument("--id",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    units=json.loads(Path(a.units).read_text(encoding="utf-8"))
    if isinstance(units,dict): units=units.get("units",[])
    profiles=load_profiles(a.profiles)
    out=build(a.profile,units,profiles,mock_id=a.id)
    Path(a.out).write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(a.out)
