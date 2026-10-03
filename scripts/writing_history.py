#!/usr/bin/env python3
"""Durable-friendly, language-agnostic learning history for Abel.

SQLite is the local source-of-truth cache. Snapshot/export layers can publish
language-specific summaries to Google Drive without changing the learning schema.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2
DEFAULT_LANGUAGE = "zh-CN"


def connect(db_path: str | Path = "data/abel_learning.db") -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS writing_corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key TEXT NOT NULL UNIQUE,
            language TEXT NOT NULL DEFAULT 'zh-CN',
            original TEXT NOT NULL,
            minimal_correction TEXT NOT NULL,
            natural_version TEXT NOT NULL,
            advanced_version TEXT NOT NULL,
            target_level TEXT NOT NULL,
            register_name TEXT NOT NULL,
            hsk_score REAL,
            severity TEXT,
            confidence TEXT,
            engine_version TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            result_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS writing_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            correction_id INTEGER NOT NULL,
            issue_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            original_span TEXT,
            correction TEXT,
            rule TEXT,
            FOREIGN KEY(correction_id) REFERENCES writing_corrections(id)
        );

        CREATE TABLE IF NOT EXISTS vocabulary_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            correction_id INTEGER NOT NULL,
            word TEXT NOT NULL,
            word_id TEXT,
            status TEXT NOT NULL,
            note_ko TEXT,
            FOREIGN KEY(correction_id) REFERENCES writing_corrections(id)
        );

        CREATE INDEX IF NOT EXISTS idx_writing_issues_type
            ON writing_issues(issue_type);
        CREATE INDEX IF NOT EXISTS idx_vocab_usage_word
            ON vocabulary_usage(word);
        CREATE INDEX IF NOT EXISTS idx_writing_language
            ON writing_corrections(language);
        """
    )
    # Backward-compatible migration for databases created by v1.
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(writing_corrections)")}
    if "language" not in cols:
        conn.execute(
            "ALTER TABLE writing_corrections ADD COLUMN language TEXT NOT NULL DEFAULT 'zh-CN'"
        )
        conn.commit()
    return conn


def record_correction(
    result: dict[str, Any],
    *,
    language: str = DEFAULT_LANGUAGE,
    db_path: str | Path = "data/abel_learning.db",
) -> int:
    cache_key = str(result.get("cache_key") or "").strip()
    if not cache_key:
        raise ValueError("result.cache_key is required.")

    original = str(result.get("original") or "").strip()
    versions = result.get("versions") or {"minimal_correction": result.get("minimal_correction"), "natural_version": result.get("natural_version"), "advanced_version": result.get("advanced_version")}
    assessment = result.get("assessment") or result.get("hsk") or {}
    if not original or any(not str(versions.get(k) or "").strip()
                           for k in ("minimal_correction", "natural_version", "advanced_version")):
        raise ValueError("original and all correction versions are required.")

    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT id FROM writing_corrections WHERE cache_key = ?", (cache_key,)
        ).fetchone()
        if row:
            return int(row["id"])

        cur = conn.execute(
            """
            INSERT INTO writing_corrections (
                cache_key, language, original, minimal_correction, natural_version,
                advanced_version, target_level, register_name, hsk_score, severity,
                confidence, engine_version, prompt_version, result_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cache_key,
                str(result.get("language") or language or DEFAULT_LANGUAGE),
                original,
                versions["minimal_correction"],
                versions["natural_version"],
                versions["advanced_version"],
                str(assessment.get("target_level") or result.get("target_level") or "GENERAL"),
                str(result.get("register") or "neutral"),
                assessment.get("score"),
                str((result.get("overall") or {}).get("severity") or "none"),
                str(result.get("confidence") or "unknown"),
                str(result.get("version") or ""),
                str(result.get("prompt_version") or ""),
                json.dumps(result, ensure_ascii=False, sort_keys=True),
            ),
        )
        correction_id = int(cur.lastrowid)

        for issue in result.get("issues", []):
            if not isinstance(issue, dict):
                continue
            conn.execute(
                """INSERT INTO writing_issues
                   (correction_id, issue_type, severity, original_span, correction, rule)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    correction_id,
                    str(issue.get("type") or "unknown"),
                    str(issue.get("severity") or "minor"),
                    str(issue.get("span") or issue.get("original") or ""),
                    str(issue.get("correction") or ""),
                    str(issue.get("rule") or ""),
                ),
            )

        for usage in result.get("vocabulary_usage", []):
            if not isinstance(usage, dict) or not str(usage.get("word") or "").strip():
                continue
            conn.execute(
                """INSERT INTO vocabulary_usage
                   (correction_id, word, word_id, status, note_ko)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    correction_id,
                    str(usage["word"]),
                    str(usage.get("word_id")) if usage.get("word_id") is not None else None,
                    str(usage.get("status") or "unknown"),
                    str(usage.get("note_ko") or ""),
                ),
            )

        conn.commit()
        return correction_id
    finally:
        conn.close()


def error_summary(*, language: str | None = None, db_path: str | Path = "data/abel_learning.db") -> list[dict[str, Any]]:
    conn = connect(db_path)
    try:
        if language:
            rows = conn.execute(
                """SELECT w.issue_type, w.severity, COUNT(*) AS count
                   FROM writing_issues w JOIN writing_corrections c ON c.id=w.correction_id
                   WHERE c.language=? GROUP BY w.issue_type,w.severity
                   ORDER BY count DESC,w.issue_type ASC""", (language,)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT issue_type, severity, COUNT(*) AS count
                   FROM writing_issues GROUP BY issue_type,severity
                   ORDER BY count DESC,issue_type ASC"""
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def vocabulary_summary(*, language: str | None = None, db_path: str | Path = "data/abel_learning.db") -> list[dict[str, Any]]:
    conn = connect(db_path)
    try:
        where = "WHERE c.language=?" if language else ""
        params = (language,) if language else ()
        rows = conn.execute(
            f"""SELECT v.word,
                       SUM(CASE WHEN v.status='incorrect' THEN 1 ELSE 0 END) AS incorrect_count,
                       SUM(CASE WHEN v.status='awkward' THEN 1 ELSE 0 END) AS awkward_count,
                       COUNT(*) AS total_uses
                FROM vocabulary_usage v JOIN writing_corrections c ON c.id=v.correction_id
                {where}
                GROUP BY v.word
                ORDER BY incorrect_count DESC,awkward_count DESC,total_uses DESC,v.word ASC""",
            params,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
