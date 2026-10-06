#!/usr/bin/env python3
"""Build a deterministic daily review queue from Abel learning history.

No new learning content is invented. Queue items are source-backed practice
questions recorded by Abel, with active spaced-review state applied.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from learning_session import connect as connect_learning
from review_state_engine import connect as connect_review

SCHEMA = "abel.learning.daily-queue.v1"


def _parse_review_time(value: str):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _priority(wrong: int, last_seen: str | None, error_type: str | None) -> float:
    age_days = 999.0
    if last_seen:
        try:
            dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
            age_days = max(
                0.0,
                (datetime.now(timezone.utc) - dt).total_seconds() / 86400,
            )
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

    db_path = Path(db_path)

    # learning_session owns the durable learning schema, including
    # practice_errors. review_state_engine owns review_states.
    connect_review(db_path).close()
    con = connect_learning(db_path)
    con.row_factory = sqlite3.Row

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    now_iso = datetime.now(timezone.utc).isoformat()

    rows = con.execute(
        """SELECT question_id, resource_id, kind, level, error_type,
                  COUNT(*) AS wrong_count, MAX(occurred_at) AS last_seen
           FROM practice_errors
           WHERE language=? AND occurred_at >= ?
           GROUP BY question_id, resource_id, kind, level, error_type
           ORDER BY wrong_count DESC, last_seen DESC, question_id""",
        (language, cutoff),
    ).fetchall()

    candidates = []
    seen = set()

    for r in rows:
        if not r["resource_id"]:
            continue
        key = (str(r["question_id"]), str(r["resource_id"]))
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "question_id": r["question_id"],
                "resource_id": r["resource_id"],
                "kind": r["kind"],
                "level": r["level"],
                "error_type": r["error_type"],
                "wrong_count": int(r["wrong_count"]),
                "last_seen": r["last_seen"],
                "priority": _priority(
                    int(r["wrong_count"]), r["last_seen"], r["error_type"]
                ),
            }
        )

    # Latest recorded error metadata for due spaced-review items.
    latest_errors = {}
    latest_rows = con.execute(
        """SELECT pe.question_id, pe.resource_id, pe.error_type
           FROM practice_errors pe
           JOIN (
             SELECT language, question_id, resource_id, MAX(id) AS max_id
             FROM practice_errors
             WHERE language=? AND resource_id IS NOT NULL
             GROUP BY language, question_id, resource_id
           ) latest ON latest.max_id=pe.id""",
        (language,),
    ).fetchall()
    for r in latest_rows:
        latest_errors[(str(r["question_id"]), str(r["resource_id"]))] = r["error_type"]

    review_rows = con.execute(
        """SELECT *
           FROM review_states
           WHERE language=? AND status='active' AND next_review_at<=?
           ORDER BY next_review_at ASC, wrong_count DESC, question_id ASC""",
        (language, now_iso),
    ).fetchall()

    for r in review_rows:
        key = (str(r["question_id"]), str(r["resource_id"]))
        if not r["resource_id"] or key in seen:
            continue
        seen.add(key)
        error_type = latest_errors.get(key)
        candidates.append(
            {
                "question_id": r["question_id"],
                "resource_id": r["resource_id"],
                "kind": r["kind"],
                "level": r["level"],
                "error_type": error_type,
                "wrong_count": int(r["wrong_count"]),
                "last_seen": r["last_seen"],
                "priority": _priority(
                    int(r["wrong_count"]), r["last_seen"], error_type
                )
                + 0.5,
            }
        )

    # Enrich every candidate with its durable review state.
    states = {
        (str(r["question_id"]), str(r["resource_id"])): dict(r)
        for r in con.execute(
            "SELECT * FROM review_states WHERE language=?",
            (language,),
        ).fetchall()
    }
    con.close()

    now = datetime.now(timezone.utc)
    enriched = []
    for item in candidates:
        state = states.get((str(item["question_id"]), str(item["resource_id"])))
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
                item["review_reason"] = (
                    "overdue"
                    if next_review < now
                    else "due"
                    if item["due"]
                    else "scheduled"
                )
            except ValueError:
                item["due"] = False
                item["review_reason"] = "scheduled"
        else:
            item["review_state"] = None
            item["due"] = True
            item["review_reason"] = "new"

        enriched.append(item)

    enriched.sort(
        key=lambda x: (
            0 if x["due"] else 1,
            x["review_state"]["next_review_at"] if x["review_state"] else "",
            -x["priority"],
            -x["wrong_count"],
            x["question_id"],
        )
    )
    queue = enriched[:limit]

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
            "errors_only": False,
            "spaced_review_due": True,
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
    Path(a.out).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(a.out)


if __name__ == "__main__":
    main()
