#!/usr/bin/env python3
"""Abel writing practice envelope around the multilingual correction engine."""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from scripts.multilingual_writing_engine import make_envelope, validate_result

SCHEMA="abel.learning.writing.v1"

def prepare(resource):
    required=("id","language","level","prompt")
    missing=[k for k in required if not resource.get(k)]
    if missing:
        raise ValueError("missing: "+",".join(missing))
    return {
        "schema_version":SCHEMA,
        "resource_id":resource["id"],
        "language":resource["language"],
        "level":resource["level"],
        "prompt":resource["prompt"],
        "context":resource.get("context",""),
        "source":resource.get("source"),
        "source_links":resource.get("source_links",[]),
        "status":"ready_for_correction"
    }

def finalize(resource, text, correction_result):
    errors=validate_result(correction_result,text)
    if errors:
        raise ValueError("invalid correction result: "+"; ".join(errors))
    return {
        "schema_version":SCHEMA,
        "resource_id":resource["id"],
        "language":resource["language"],
        "level":resource["level"],
        "input":text,
        "correction":correction_result,
        "source":resource.get("source"),
        "source_links":resource.get("source_links",[]),
        "completed_at":datetime.now(timezone.utc).isoformat()
    }

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("resource")
    p.add_argument("text")
    p.add_argument("--target-level")
    p.add_argument("--register",default="neutral")
    p.add_argument("--out",required=True)
    a=p.parse_args()
    resource=json.load(open(a.resource,encoding="utf-8"))
    prepared=prepare(resource)
    target=a.target_level or resource["level"]
    envelope=make_envelope(
        a.text,language=resource["language"],target_level=target,
        register=a.register,context=resource.get("context",""),
        known_words=resource.get("known_words",[])
    )
    out={**prepared,"correction_request":envelope}
    json.dump(out,open(a.out,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
    print(a.out)
