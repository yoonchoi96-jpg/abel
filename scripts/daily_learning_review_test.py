from __future__ import annotations

import json
import sqlite3

import pytest

from daily_learning_review import execute_review


def _queue():
    return {
        "schema_version": "abel.learning.daily-queue.v1",
        "language": "zh-CN",
        "source_of_truth": "Abel",
        "items": [
            {
                "question_id": "q1",
                "resource_id": "r1",
                "kind": "reading",
                "level": "HSK6",
                "error_type": "grammar",
            },
            {
                "question_id": "q2",
                "resource_id": "r2",
                "kind": "listening",
                "level": "HSK6",
                "error_type": "vocabulary",
            },
        ],
    }


def test_execute_review_updates_review_state(tmp_path):
    db = tmp_path / "learning.db"
    result = execute_review(
        "zh-CN",
        _queue(),
        [
            {
                "question_id": "q1",
                "resource_id": "r1",
                "correct": True,
                "at": "2026-10-04T00:00:00+00:00",
            },
            {
                "question_id": "q2",
                "resource_id": "r2",
                "correct": False,
                "at": "2026-10-04T00:00:00+00:00",
            },
        ],
        db_path=db,
    )
    assert result["schema_version"] == "abel.learning.daily-review.v1"
    assert result["source_of_truth"] == "Abel"
    assert result["api_calls"] == 0
    assert result["completed_count"] == 2

    con = sqlite3.connect(db)
    rows = con.execute(
        "SELECT question_id,correct_count,wrong_count,last_result,next_review_at "
        "FROM review_states WHERE language='zh-CN' ORDER BY question_id"
    ).fetchall()
    con.close()
    assert rows[0][0] == "q1"
    assert rows[0][1:] == (1, 0, "correct", "2026-10-05T00:00:00+00:00")
    assert rows[1][0] == "q2"
    assert rows[1][1:] == (0, 1, "wrong", "2026-10-04T00:00:00+00:00")


def test_execute_review_rejects_unknown_source_item(tmp_path):
    with pytest.raises(ValueError, match="not present"):
        execute_review(
            "zh-CN",
            _queue(),
            [{"question_id": "qx", "resource_id": "rx", "correct": True}],
            db_path=tmp_path / "learning.db",
        )


def test_execute_review_rejects_wrong_language(tmp_path):
    with pytest.raises(ValueError, match="language"):
        execute_review(
            "fr-FR",
            _queue(),
            [{"question_id": "q1", "resource_id": "r1", "correct": True}],
            db_path=tmp_path / "learning.db",
        )
