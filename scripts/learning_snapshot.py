#!/usr/bin/env python3
"""Build language-specific learning snapshots for Gemini."""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from writing_history import connect, error_summary, vocabulary_summary

def build_snapshot(language: str, db_path: str | Path) -> dict[str, Any]:
    conn = connect(db_path)
    try:
        stats = conn.execute(
            """SELECT COUNT(*) AS corrections, MIN(created_at) AS first_correction,
                      MAX(created_at) AS last_correction, AVG(hsk_score) AS average_score
               FROM writing_corrections WHERE language=?""", (language,)
        ).fetchone()
        recent = conn.execute(
            """SELECT original,minimal_correction,natural_version,advanced_version,
                      target_level,register_name,hsk_score,severity,confidence,created_at
               FROM writing_corrections WHERE language=? ORDER BY id DESC LIMIT 20""",
            (language,)
        ).fetchall()
    finally:
        conn.close()
    return {
        "schema_version": "abel.learning.snapshot.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "language": language,
        "source": "Abel local learning history",
        "stats": dict(stats),
        "recurring_errors": error_summary(language=language, db_path=db_path),
        "problematic_vocabulary": vocabulary_summary(language=language, db_path=db_path),
        "recent_corrections": [dict(x) for x in recent],
        "gemini_instructions": {
            "use_as_context": True,
            "treat_as_learning_history_not_truth": True,
            "prioritize_recurring_patterns": True,
            "do_not_invent_history": True,
        },
    }

def render_markdown(snapshot: dict[str, Any]) -> str:
    s = snapshot["stats"]
    lines = [
        "# Abel Learning Snapshot", "",
        f"Language: {snapshot['language']}",
        f"Generated: {snapshot['generated_at']}",
        f"Corrections recorded: {s.get('corrections', 0)}",
        f"First correction: {s.get('first_correction') or '-'}",
        f"Last correction: {s.get('last_correction') or '-'}",
        f"Average descriptive writing score: {round(s['average_score'], 1) if s.get('average_score') is not None else '-'}",
        "", "## Recurring errors",
    ]
    if snapshot["recurring_errors"]:
        for x in snapshot["recurring_errors"][:20]:
            lines.append(f"- {x['issue_type']} / {x['severity']}: {x['count']}")
    else:
        lines.append("- No recorded errors yet.")
    lines += ["", "## Problematic vocabulary"]
    if snapshot["problematic_vocabulary"]:
        for x in snapshot["problematic_vocabulary"][:30]:
            lines.append(
                f"- {x['word']} — incorrect {x['incorrect_count']}, "
                f"awkward {x['awkward_count']}, total {x['total_uses']}"
            )
    else:
        lines.append("- No vocabulary-usage history yet.")
    lines += ["", "## Recent corrections"]
    for x in snapshot["recent_corrections"][:10]:
        lines += [
            "", f"### {x['created_at']} · {x['target_level']}",
            f"Original: {x['original']}",
            f"Minimal: {x['minimal_correction']}",
            f"Natural: {x['natural_version']}",
            f"Advanced: {x['advanced_version']}",
        ]
    lines += [
        "", "## Gemini usage rules",
        "- Use this file to adapt exercises to recurring weaknesses.",
        "- Do not claim a historical error unless it appears in this snapshot.",
        "- Prefer repeated patterns over one-off mistakes.",
        "- Do not lower target difficulty unless explicitly requested.",
    ]
    return "\n".join(lines) + "\n"

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--language", default="")
    p.add_argument("--all", action="store_true")
    p.add_argument("--db", default="data/abel_learning.db")
    p.add_argument("--out", default="data/learning_snapshots")
    args = p.parse_args()
    conn = connect(args.db)
    try:
        langs = [r[0] for r in conn.execute(
            "SELECT DISTINCT language FROM writing_corrections ORDER BY language"
        )]
    finally:
        conn.close()
    if args.language:
        langs = [args.language]
    elif not args.all:
        langs = langs[:1] if langs else ["zh-CN"]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for language in langs:
        snap = build_snapshot(language, args.db)
        stem = language.replace("/", "_")
        (out / f"{stem}.json").write_text(
            json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (out / f"{stem}.md").write_text(render_markdown(snap), encoding="utf-8")
    index = {
        "schema_version": "abel.learning.index.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "languages": langs,
        "files": [f"{x}.md" for x in langs] + [f"{x}.json" for x in langs],
    }
    (out / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

if __name__ == "__main__":
    main()
