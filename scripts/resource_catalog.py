#!/usr/bin/env python3
"""Abel Learning resource catalog.

Consumes an external manifest (for example a Google Drive scan) and produces
an immutable, deduplicated catalog. It never invents files and never modifies
source metadata.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

SCHEMA="abel.resource.catalog.v1"
KINDS={"listening","reading","writing","mock_test","reference"}

def _stable_id(item):
    raw=json.dumps({
        "path":item.get("path"),
        "name":item.get("name"),
        "size":item.get("size"),
        "checksum":item.get("checksum"),
    },ensure_ascii=False,sort_keys=True)
    return "res-"+hashlib.sha256(raw.encode()).hexdigest()[:20]

def build(manifest):
    if isinstance(manifest,dict):
        items=manifest.get("items",[])
    else:
        items=manifest
    if not isinstance(items,list):
        raise ValueError("manifest.items must be a list")
    out=[]; seen={}
    for src in items:
        if not isinstance(src,dict):
            raise ValueError("each manifest item must be an object")
        item=dict(src)
        item["resource_id"]=item.get("resource_id") or _stable_id(item)
        item["kind"]=item.get("kind") or item.get("type")
        if item["kind"] not in KINDS:
            raise ValueError(f"invalid kind: {item.get('kind')}")
        item.setdefault("language","")
        item.setdefault("exam_system","")
        item.setdefault("level","")
        item.setdefault("files",[])
        key=item.get("checksum") or item.get("path") or item["resource_id"]
        if key in seen:
            # Preserve the first source record; do not silently merge conflicting data.
            if seen[key] != item:
                raise ValueError(f"conflicting duplicate resource: {key}")
            continue
        seen[key]=item
        out.append(item)
    out.sort(key=lambda x:(x.get("language",""),x.get("kind",""),x["resource_id"]))
    return {"schema_version":SCHEMA,"count":len(out),"items":out}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("input"); p.add_argument("--out",required=True)
    a=p.parse_args()
    data=json.loads(Path(a.input).read_text(encoding="utf-8"))
    Path(a.out).write_text(json.dumps(build(data),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
