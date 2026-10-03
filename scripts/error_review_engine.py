#!/usr/bin/env python3
"""Abel error/review engine.

Turns scored practice results into deterministic review priorities.
It stores no invented explanations; it only derives priorities from recorded
results and optional error metadata.
"""
from __future__ import annotations
import argparse, json, math
from datetime import datetime, timezone

SCHEMA="abel.learning.error-review.v1"

def build_review(results, now=None):
    now=now or datetime.now(timezone.utc)
    rows=[]
    for r in results:
        if r.get("correct") is True:
            continue
        qid=str(r.get("question_id",""))
        if not qid:
            continue
        severity=float(r.get("severity",1.0) or 1.0)
        attempts=int(r.get("attempts",1) or 1)
        wrong=int(r.get("wrong_count",1) or 1)
        recency_hours=float(r.get("recency_hours",0) or 0)
        recency=1.0/(1.0+recency_hours/24.0)
        priority=severity*(1+math.log1p(wrong))*recency/(1+0.15*max(0,attempts-1))
        rows.append({"question_id":qid,"priority":round(priority,6),
                     "error_type":r.get("error_type"),
                     "resource_id":r.get("resource_id"),"kind":r.get("kind"),
                     "language":r.get("language"),
                     "level":r.get("level")})
    rows.sort(key=lambda x:(-x["priority"],x["question_id"]))
    return {"schema_version":SCHEMA,"generated_at":now.isoformat(),
            "count":len(rows),"items":rows}

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("input"); p.add_argument("--out",required=True)
    a=p.parse_args()
    data=json.load(open(a.input,encoding="utf-8"))
    results=data.get("results",data) if isinstance(data,(dict,list)) else []
    json.dump(build_review(results),open(a.out,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
    print(a.out)
