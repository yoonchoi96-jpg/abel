#!/usr/bin/env python3
"""Abel end-to-end deterministic learning pipeline.

Flow:
scored results -> error review -> adaptive plan -> session events -> snapshot.
It consumes only source-backed scored records and never invents learning content.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any

from error_review_engine import build_review
from adaptive_learning_plan import build_plan
from learning_session import record_session
from learning_snapshot import build_snapshot

SCHEMA = "abel.learning.pipeline.v1"

def _session_from_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "language": result["language"],
        "session_type": result.get("kind", "practice"),
        "resource_id": result.get("unit_id") or result.get("resource_id"),
        "level": result.get("level"),
        "started_at": result.get("started_at") or result.get("completed_at") or __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "duration_seconds": result.get("duration_seconds"),
        "score": result.get("score"),
        "total": result.get("total"),
        "correct": result.get("correct"),
        "payload": result,
    }

def _review_inputs(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for parent in results:
        for item in parent.get("results", []):
            row = dict(item)
            row.update({
                "kind": parent.get("kind"),
                "resource_id": parent.get("unit_id") or parent.get("resource_id"),
                "language": parent.get("language"),
                "level": parent.get("level"),
            })
            rows.append(row)
    return rows

def run(results: list[dict[str, Any]], db_path: str | Path,
        limits: dict[str, int] | None = None) -> dict[str, Any]:
    if not isinstance(results, list) or not results:
        raise ValueError("results must be a non-empty list")
    languages = {x.get("language") for x in results if x.get("language")}
    if len(languages) != 1:
        raise ValueError("pipeline run must contain exactly one language")
    for result in results:
        if not result.get("language") or not result.get("kind"):
            raise ValueError("each result needs language and kind")
        record_session(_session_from_result(result), db_path)

    review = build_review(_review_inputs(results))
    candidates = [
        {
            "id": item["question_id"],
            "kind": item.get("kind"),
            "priority": item["priority"],
            "resource_id": item.get("resource_id"),
            "language": item.get("language"),
            "level": item.get("level"),
            "error_type": item.get("error_type"),
        }
        for item in review["items"]
        if item.get("kind")
    ]
    plan = build_plan(candidates, limits)
    snapshot = build_snapshot(next(iter(languages)), db_path)
    return {
        "schema_version": SCHEMA,
        "language": next(iter(languages)),
        "sessions_recorded": len(results),
        "error_review": review,
        "adaptive_plan": plan,
        "snapshot": snapshot,
    }

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("results")
    p.add_argument("--db", default="data/abel_learning.db")
    p.add_argument("--limits")
    p.add_argument("--out", required=True)
    a = p.parse_args()
    raw = json.loads(Path(a.results).read_text(encoding="utf-8"))
    results = raw.get("results", raw) if isinstance(raw, dict) else raw
    limits = json.loads(Path(a.limits).read_text(encoding="utf-8")) if a.limits else {}
    out = run(results, a.db, limits)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(a.out)
