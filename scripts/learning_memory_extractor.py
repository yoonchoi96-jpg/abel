#!/usr/bin/env python3
"""Extract compact, deterministic learning memory from provider event history."""
from __future__ import annotations
import json, hashlib
from collections import Counter
from typing import Any

SCHEMA = "abel.learning.memory.v1"
MAX_ITEMS = 50

def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        s = value.strip()
        if s.startswith("{") or s.startswith("["):
            try: return json.loads(s)
            except Exception: return value
    return value

def _walk(value: Any):
    value = _json_value(value)
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from _walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk(v)

def _fingerprint(kind: str, value: str) -> str:
    return hashlib.sha256(f"{kind}|{value}".encode("utf-8")).hexdigest()[:16]

def extract(events: list[dict[str, Any]], language: str) -> dict[str, Any]:
    errors = Counter()
    vocab = Counter()
    outcomes = Counter()
    seen = set()
    for event in events:
        root = event.get("output", event)
        for node in _walk(root):
            for issue in node.get("issues", []) if isinstance(node.get("issues"), list) else []:
                if not isinstance(issue, dict): continue
                key = str(issue.get("issue_type") or issue.get("error_type") or issue.get("type") or "").strip()
                if key:
                    errors[key] += 1
            usage = node.get("vocabulary_usage")
            if isinstance(usage, list):
                for item in usage:
                    if not isinstance(item, dict): continue
                    word = str(item.get("word") or "").strip()
                    status = str(item.get("status") or item.get("usage_status") or "").strip()
                    if word and status in {"incorrect", "awkward", "correct"}:
                        vocab[(word, status)] += 1
            status = str(node.get("status") or "").strip()
            if status in {"success", "executed", "failed", "fallback"}:
                outcomes[status] += 1

    error_items = [
        {"type": k, "count": n, "memory_id": _fingerprint("error", k)}
        for k, n in errors.most_common(MAX_ITEMS)
    ]
    vocab_items = [
        {"word": w, "status": s, "count": n, "memory_id": _fingerprint("vocab", f"{w}|{s}")}
        for (w, s), n in sorted(vocab.items(), key=lambda x: (-x[1], x[0]))
    ][:MAX_ITEMS]
    return {
        "schema_version": SCHEMA,
        "language": language,
        "source": "Abel provider event history",
        "event_count": len(events),
        "recurring_error_signals": error_items,
        "vocabulary_usage_signals": vocab_items,
        "provider_outcomes": dict(outcomes),
        "rules": {
            "deterministic": True,
            "raw_provider_output_not_persisted_here": True,
            "no_invented_history": True,
        },
    }

def extract_from_db(language: str, db_path="data/abel_learning.db", limit=None) -> dict[str, Any]:
    from learning_session import provider_recent
    if limit is None:
        events = _all_provider_events(language, db_path)
    else:
        events = provider_recent(language, db_path, limit=limit)
    return extract(events, language)

def _all_provider_events(language: str, db_path):
    import sqlite3
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT task_type,model,cache_key,input_summary,output_json,created_at "
            "FROM provider_learning_events WHERE language=? ORDER BY id ASC", (language,)
        ).fetchall()
    finally:
        con.close()
    out=[]
    for row in rows:
        x=dict(row)
        try: x["output"]=json.loads(x.pop("output_json"))
        except Exception: x["output"]=x.pop("output_json")
        out.append(x)
    return out

if __name__ == "__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--language", required=True)
    p.add_argument("--db", default="data/abel_learning.db")
    print(json.dumps(extract_from_db(p.parse_args().language, p.parse_args().db), ensure_ascii=False, indent=2))
