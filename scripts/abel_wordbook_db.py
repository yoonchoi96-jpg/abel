#!/usr/bin/env python3
"""Safe local Abel wordbook database layer.

This module owns the SQLite schema shared by curated HSK data and user
vocabulary imports. It contains no account access or browser automation.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DATA_ROOT = Path(os.environ.get("NAVER_WORDBOOK_DATA", "~/.naver_wordbook")).expanduser()
DB_PATH = DATA_ROOT / "naver_wordbook.sqlite3"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    # Use DB_PATH as the source of truth so tests and callers that override
    # the database path can safely point at a fresh directory.
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS wordbooks (
            id INTEGER PRIMARY KEY,
            naver_id TEXT,
            name TEXT NOT NULL,
            source_url TEXT,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            raw_json TEXT,
            UNIQUE(naver_id, name)
        );
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY,
            word TEXT NOT NULL,
            meaning TEXT,
            pronunciation TEXT,
            part_of_speech TEXT,
            example TEXT,
            source_url TEXT,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            raw_json TEXT,
            UNIQUE(word, meaning)
        );
        CREATE TABLE IF NOT EXISTS wordbook_words (
            wordbook_id INTEGER NOT NULL,
            word_id INTEGER NOT NULL,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            raw_json TEXT,
            PRIMARY KEY(wordbook_id, word_id),
            FOREIGN KEY(wordbook_id) REFERENCES wordbooks(id),
            FOREIGN KEY(word_id) REFERENCES words(id)
        );
        CREATE INDEX IF NOT EXISTS idx_wordbook_words_word ON wordbook_words(word_id);
        CREATE INDEX IF NOT EXISTS idx_wordbook_words_wordbook ON wordbook_words(wordbook_id);

        CREATE TABLE IF NOT EXISTS abel_classifications (
            word_id INTEGER PRIMARY KEY,
            classification_json TEXT NOT NULL,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            FOREIGN KEY(word_id) REFERENCES words(id)
        );

        CREATE TABLE IF NOT EXISTS hanping_vocab (
            word_id INTEGER PRIMARY KEY,
            traditional TEXT,
            starred INTEGER NOT NULL DEFAULT 0,
            note TEXT,
            record_hash TEXT NOT NULL,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            raw_json TEXT,
            FOREIGN KEY(word_id) REFERENCES words(id)
        );

        CREATE TABLE IF NOT EXISTS hanping_tags (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS hanping_vocab_tags (
            word_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY(word_id, tag_id),
            FOREIGN KEY(word_id) REFERENCES hanping_vocab(word_id) ON DELETE CASCADE,
            FOREIGN KEY(tag_id) REFERENCES hanping_tags(id) ON DELETE CASCADE
        );
        """)
        db.commit()
