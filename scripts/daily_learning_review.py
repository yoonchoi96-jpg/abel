#!/usr/bin/env python3
"""Execute a source-backed daily review queue and persist each result.

The queue is the contract: a submitted result must match an item already
present in that queue. No new question/resource identity is accepted.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from learning_session import record_session

SCHEMA = "abel.learning.daily-review.v1"


def _load(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _validate_queue(queue: dict, language: str) -> dict:
    if queue.get("schema_version") != "abel.learning.daily-queue.v1":
        raise ValueError("invalid daily queue schema")
    if queue.get("source_of_truth") != "Abel":
        raise ValueError("daily queue source_of_truth must be Abel")
    if queue.get("language") != language:
        raise ValueError("queue language does not match requested language")
    items = queue.get("items")
    if not isinstance(items, list):
        raise ValueError("queue items must be a list")
    return {
        (str(x.get("question_id")), str(x.get("resource_id"))): x
        for x in items
        if x.get("question_id") and x.get("resource_id")
    }


def execute_review(
    language: str,
    queue: dict,
    results: list[dict],
    *,
    db_path: str | Path = "data/abel_learning.db",
) -> dict:
    items = _validate_queue(queue, language)
    if not isinstance(results, list) or not results:
        raise ValueError("results must be a non-empty list")

    completed = []
    for result in results:
        question_id = str(result.get("question_id", "")).strip()
        resource_id = str(result.get("resource_id", "")).strip()
        if not question_id or not resource_id:
            raise ValueError("every result requires question_id and resource_id")
        item = items.get((question_id, resource_id))
        if item is None:
            raise ValueError(
                f"result is not present in the source-backed queue: "
                f"{question_id}/{resource_id}"
            )
        if not isinstance(result.get("correct"), bool):
            raise ValueError(f"correct must be boolean for {question_id}")
        kind = item.get("kind")
        level = item.get("level")
        started_at = result.get("at") or datetime.now(timezone.utc).isoformat()
        session_id = record_session(
            {
                "language": language,
                "session_type": kind or "review",
                "resource_id": resource_id,
                "level": level,
                "started_at": started_at,
                "score": 100 if result["correct"] else 0,
                "total": 1,
                "correct": 1 if result["correct"] else 0,
                "payload": {
                    "results": [
                        {
                            "question_id": question_id,
                            "resource_id": resource_id,
                            "correct": result["correct"],
                            "error_type": item.get("error_type"),
                        }
                    ]
                },
            },
            db_path=db_path,
        )
        completed.append(
            {
                "question_id": question_id,
                "resource_id": resource_id,
                "correct": result["correct"],
                "session_id": session_id,
            }
        )

    return {
        "schema_version": SCHEMA,
        "language": language,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "source_of_truth": "Abel",
        "api_calls": 0,
        "queue_item_count": len(items),
        "completed_count": len(completed),
        "completed": completed,
        "rules": {
            "queue_backed_only": True,
            "no_invented_questions": True,
            "review_state_updated": True,
            "api_free": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", required=True)
    parser.add_argument("--queue", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--db", default="data/abel_learning.db")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    queue = _load(args.queue)
    results = _load(args.results)
    payload = execute_review(args.language, queue, results, db_path=args.db)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(args.out)


if __name__ == "__main__":
    main()
