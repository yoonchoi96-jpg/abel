#!/usr/bin/env python3
"""Abel deterministic daily learning-plan builder.

This is scheduling logic only. It never invents learning resources.
"""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone

SCHEMA="abel.learning.plan.v1"
KINDS=("listening","reading","writing","mock_test")

def build_plan(candidates, limits=None):
    limits=limits or {}
    remaining={k:int(limits.get(k,999999)) for k in KINDS}
    selected=[]
    for item in sorted(candidates,key=lambda x:(-float(x.get("priority",0)),str(x.get("id","")))):
        kind=item.get("kind")
        if kind not in remaining or remaining[kind]<=0: continue
        selected.append(item)
        remaining[kind]-=1
    return {"schema_version":SCHEMA,"generated_at":datetime.now(timezone.utc).isoformat(),
            "items":selected,"count":len(selected)}

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("input"); p.add_argument("--out",required=True)
    a=p.parse_args()
    data=json.load(open(a.input,encoding="utf-8"))
    candidates=data.get("items",[]) if isinstance(data,dict) else data
    limits=json.load(open(a.limits,encoding="utf-8")) if hasattr(a,"limits") and a.limits else {}
    json.dump(build_plan(candidates,limits),open(a.out,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
    print(a.out)
