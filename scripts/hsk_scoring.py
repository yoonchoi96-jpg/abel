#!/usr/bin/env python3
"""Profile-aware HSK scoring.

This module converts source-backed section results into the reporting shape
defined by Abel's HSK exam profiles. It never fabricates HSK7-9 IRT parameters.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any

SCHEMA="abel.hsk.scoring.v1"

def load_profiles(path="data/hsk_exam_profiles.json"):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version")!="abel.hsk.exam-profiles.v1":
        raise ValueError("invalid HSK profile schema")
    return data["profiles"]

def _section_map(profile):
    return {x["kind"]:x for x in profile["sections"]}

def score_mock(mock_result: dict[str,Any], profile: dict[str,Any]) -> dict[str,Any]:
    if not isinstance(mock_result,dict):
        raise ValueError("mock_result must be an object")
    if mock_result.get("language")!="zh-CN":
        raise ValueError("HSK scoring requires zh-CN")
    sections=mock_result.get("sections")
    if not isinstance(sections,list):
        raise ValueError("mock_result.sections must be an array")
    specs=_section_map(profile)
    seen=set()
    out_sections=[]
    for section in sections:
        kind=section.get("kind")
        if kind not in specs:
            raise ValueError(f"unexpected section: {kind}")
        if kind in seen:
            raise ValueError(f"duplicate section: {kind}")
        seen.add(kind)
        spec=specs[kind]
        total=section.get("total")
        correct=section.get("correct")
        if not isinstance(total,int) or total<=0 or not isinstance(correct,int) or correct<0 or correct>total:
            raise ValueError(f"invalid result counts for {kind}")
        if total != spec["items"]:
            raise ValueError(f"{kind} expected {spec['items']} items, got {total}")
        percent=round(correct/total*100,2)
        out_sections.append({
            "kind":kind,
            "items":total,
            "correct":correct,
            "raw_percent":percent,
            "reported_score":percent,
            "score_max":spec["score_max"],
        })
    expected={x["kind"] for x in profile["sections"]}
    if seen != expected:
        raise ValueError("all profile sections must be present")
    out_sections.sort(key=lambda x:list(specs).index(x["kind"]))
    if profile["level"] in ("HSK5","HSK6"):
        total_score=round(sum(x["reported_score"] for x in out_sections),2)
        return {
            "schema_version":SCHEMA,
            "profile_id":next(k for k,v in load_profiles().items() if v is profile) if False else None,
            "level":profile["level"],
            "scoring_model":profile["scoring_model"],
            "sections":out_sections,
            "total_score":total_score,
            "total_score_max":profile["total_score_max"],
            "calibration_status":"official_section_weighting_not_reimplemented; section percentages used as mock report scores",
            "official_equivalence":False,
        }
    return {
        "schema_version":SCHEMA,
        "level":profile["level"],
        "scoring_model":profile["scoring_model"],
        "sections":out_sections,
        "total_score":None,
        "total_score_max":None,
        "calibration_status":"not_calibrated",
        "official_equivalence":False,
        "level_evaluation":None,
        "note":"HSK7-9 reported scores and level evaluation require calibrated official IRT parameters; Abel does not invent them.",
    }

def score_profile(profile_id, mock_result, profiles=None):
    profiles=profiles or load_profiles()
    if profile_id not in profiles:
        raise ValueError("unknown profile: "+profile_id)
    result=score_mock(mock_result,profiles[profile_id])
    result["profile_id"]=profile_id
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("profile")
    p.add_argument("result")
    p.add_argument("--profiles",default="data/hsk_exam_profiles.json")
    p.add_argument("--out",required=True)
    a=p.parse_args()
    profiles=load_profiles(a.profiles)
    raw=json.loads(Path(a.result).read_text(encoding="utf-8"))
    out=score_profile(a.profile,raw,profiles)
    Path(a.out).write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(a.out)
