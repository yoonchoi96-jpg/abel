#!/usr/bin/env python3
"""Build a deterministic daily review queue from Abel learning history.

No new learning content is invented. Every queue item points to a previously
recorded practice question/resource or is omitted when source identity is absent.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from review_state_engine import connect as connect_review

def _parse_review_time(value: str):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = "abel.learning.daily-queue.v1"


def _priority(wrong: int, last_seen: str | None, error_type: str | None) -> float:
    age_days = 999.0
    if last_seen:
        try:
            dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
            age_days = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400)
        except ValueError:
            pass
    recency = min(age_days, 30.0) / 30.0
    type_bonus = 1.0 if error_type else 0.0
    return round(wrong * 10.0 + recency * 5.0 + type_bonus, 3)


def build_queue(language: str, db_path: str | Path, limit: int = 20, days: int = 7) -> dict:
    if not language:
        raise ValueError("language is required")
    if limit < 1 or limit > 100:
        raise ValueError("limit must be 1..100")
    if days < 1 or days > 365:
        raise ValueError("days must be 1..365")

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    connect_review(db_path).close()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = con.execute(
        """SELECT question_id, resource_id, kind, level, error_type,
                  COUNT(*) AS wrong_count, MAX(occurred_at) AS last_seen
           FROM practice_errors
           WHERE language=? AND occurred_at >= ?
           GROUP BY question_id, resource_id, kind, level, error_type
           ORDER BY wrong_count DESC, last_seen DESC, question_id""",
        (language, cutoff),
    ).fetchall()
    con.close()

    candidates = []
    for r in rows:
        if not r["resource_id"]:
            continue
        candidates.append({
            "question_id": r["question_id"],
            "resource_id": r["resource_id"],
            "kind": r["kind"],
            "level": r["level"],
            "error_type": r["error_type"],
            "wrong_count": int(r["wrong_count"]),
            "last_seen": r["last_seen"],
            "priority": _priority(int(r["wrong_count"]), r["last_seen"], r["error_type"]),
        })
    review_con = connect_review(db_path)
    review_rows = review_con.execute(
        "SELECT * FROM review_states WHERE language=?",
        (language,),
    ).fetchall()
    review_con.close()
    states = {(r["question_id"], r["resource_id"]): dict(r) for r in review_rows}
    now = datetime.now(timezone.utc)
    for item in candidates:
        state = states.get((item["question_id"], item["resource_id"]))
        if state and state["status"] == "mastered":
            continue
        if state:
            item["review_state"] = {
                "review_count": state["review_count"],
                "correct_count": state["correct_count"],
                "wrong_count": state["wrong_count"],
                "consecutive_correct": state["consecutive_correct"],
                "consecutive_wrong": state["consecutive_wrong"],
                "last_result": state["last_result"],
                "interval_days": state["interval_days"],
                "next_review_at": state["next_review_at"],
                "status": state["status"],
            }
            try:
                next_review = _parse_review_time(state["next_review_at"])
                item["due"] = next_review <= now
                if item["due"]:
                    item["review_reason"] = "overdue" if next_review < now else "due"
                else:
                    item["review_reason"] = "scheduled"
            except ValueError:
                item["due"] = False
                item["review_reason"] = "scheduled"
        else:
            item["review_state"] = None
            item["due"] = True
            item["review_reason"] = "new"

    candidates.sort(
        key=lambda x: (
            0 if x["due"] else 1,
            x["review_state"]["next_review_at"] if x["review_state"] else "",
            -x["priority"],
            -x["wrong_count"],
            x["question_id"],
        )
    )
    queue = candidates[:limit]

    return {
        "schema_version": SCHEMA,
        "language": language,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": days,
        "limit": limit,
        "item_count": len(queue),
        "source_of_truth": "Abel",
        "api_calls": 0,
        "rules": {
            "source_backed_only": True,
            "no_invented_questions": True,
            "errors_only": True,
            "deterministic_order": True,
        },
        "items": queue,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--language", required=True)
    p.add_argument("--db", default="data/abel_learning.db")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    payload = build_queue(a.language, a.db, a.limit, a.days)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(a.out)


if __name__ == "__main__":
    main()
