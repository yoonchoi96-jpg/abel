#!/usr/bin/env python3
"""Validate/build a question-bank manifest supplied from an external Drive scan."""
from __future__ import annotations
import argparse, json
from pathlib import Path
SCHEMA="abel.question-bank.index.v1"
FIELDS=("id","title","type","level","exam_system","source","files","related_items","status")

def build(items):
    out=[]
    for x in items:
        item={k:x.get(k) for k in FIELDS}
        item["files"]=item["files"] or []
        item["related_items"]=item["related_items"] or []
        item["status"]=item["status"] or "unknown"
        if not item["id"] or not item["title"] or item["type"] not in {"listening","reading","writing","mock_test","reference"}:
            raise ValueError("invalid question-bank item: "+json.dumps(x,ensure_ascii=False))
        out.append(item)
    return {"schema_version":SCHEMA,"items":out,"count":len(out)}

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("input"); p.add_argument("--out",required=True)
    a=p.parse_args(); data=json.loads(Path(a.input).read_text(encoding="utf-8"))
    items=data["items"] if isinstance(data,dict) else data
    Path(a.out).write_text(json.dumps(build(items),ensure_ascii=False,indent=2),encoding="utf-8")
