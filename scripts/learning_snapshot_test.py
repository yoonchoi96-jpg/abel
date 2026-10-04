#!/usr/bin/env python3
from learning_snapshot import render_markdown

def test_render_markdown_exposes_learning_memory_context():
    snapshot = {
        "language": "zh-CN",
        "generated_at": "2026-10-04T00:00:00+00:00",
        "stats": {
            "corrections": 0,
            "first_correction": None,
            "last_correction": None,
            "average_score": None,
        },
        "learning_sessions": {"session_types": []},
        "recurring_errors": [],
        "problematic_vocabulary": [],
        "recent_corrections": [],
        "learning_memory": {
            "event_count": 4,
            "recurring_error_signals": [{
                "type": "word_choice",
                "count": 3,
                "task_types": ["translation", "chinese_explanation"],
                "first_seen": "2026-10-01T00:00:00+00:00",
                "last_seen": "2026-10-03T00:00:00+00:00",
            }],
            "vocabulary_usage_signals": [{
                "word": "维护",
                "status": "incorrect",
                "count": 2,
                "task_types": ["translation"],
                "first_seen": "2026-10-02T00:00:00+00:00",
                "last_seen": "2026-10-03T00:00:00+00:00",
            }],
        },
    }
    markdown = render_markdown(snapshot)
    assert "word_choice: 3" in markdown
    assert "tasks: translation, chinese_explanation" in markdown
    assert "first 2026-10-01T00:00:00+00:00" in markdown
    assert "last 2026-10-03T00:00:00+00:00" in markdown
    assert "维护 / incorrect: 2" in markdown
    assert "tasks: translation" in markdown
