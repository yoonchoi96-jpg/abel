#!/usr/bin/env python3
"""Upsert normalized Hanping vocabulary into Abel's shared local DB."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

try:
    from scripts import abel_wordbook_db as db_layer
except ModuleNotFoundError:
    import abel_wordbook_db as db_layer

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "hanping" / "normalized.json"
HANPING_BOOK = "Hanping"

DB_PATH = db_layer.DB_PATH
now_iso = db_layer.now_iso


def init_db() -> None:
    """Initialize the shared schema using this module's active DB_PATH."""
    db_layer.DB_PATH = DB_PATH
    db_layer.init_db()


def _resolve_word_id(db, word: str, pinyin: str | None):
    """Resolve Hanping to the strongest existing Abel lexical row.

    Prefer an existing Hanping row, then an exact word+pinyin row (for HSK/
    dictionary enrichment), then the legacy meaning-null row. Only create a
    new row when no deterministic candidate exists.
    """
    row = db.execute(
        """SELECT w.id
           FROM words w
           JOIN hanping_vocab hv ON hv.word_id=w.id
           WHERE w.word=?
           ORDER BY w.id
           LIMIT 1""",
        (word,),
    ).fetchone()
    if row:
        return row[0]

    if pinyin:
        row = db.execute(
            """SELECT id FROM words
               WHERE word=? AND pronunciation=?
               ORDER BY id LIMIT 1""",
            (word, pinyin),
        ).fetchone()
        if row:
            return row[0]

    row = db.execute(
        """SELECT id FROM words
           WHERE word=? AND meaning IS NULL
           ORDER BY id LIMIT 1""",
        (word,),
    ).fetchone()
    return row[0] if row else None


def sync(path: Path = DEFAULT_INPUT) -> dict[str, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or payload.get("source") != "hanping":
        raise ValueError("unsupported Hanping normalized payload")

    # Validate the full payload before touching the database so a malformed
    # snapshot cannot create or partially mutate the shared DB.
    for item in payload.get("words", []):
        word = (item.get("hanzi") or item.get("simplified") or "").strip()
        if word and not item.get("record_hash"):
            raise ValueError(f"Hanping record missing record_hash: {word}")

    init_db()
    now = now_iso()
    inserted = updated = 0

    with sqlite3.connect(DB_PATH) as db:
        db.execute("PRAGMA foreign_keys=ON")
        row = db.execute(
            "SELECT id FROM wordbooks WHERE naver_id IS NULL AND name=?",
            (HANPING_BOOK,),
        ).fetchone()
        if row:
            book_id = row[0]
            db.execute("UPDATE wordbooks SET last_seen=? WHERE id=?", (now, book_id))
        else:
            db.execute(
                """INSERT INTO wordbooks(naver_id,name,source_url,first_seen,last_seen,raw_json)
                   VALUES(NULL,?,?,?,?,?)""",
                (
                    HANPING_BOOK,
                    "hanping",
                    now,
                    now,
                    json.dumps({"source": "hanping"}, ensure_ascii=False),
                ),
            )
            book_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        for item in payload.get("words", []):
            word = (item.get("hanzi") or item.get("simplified") or "").strip()
            if not word:
                continue
            pinyin = (item.get("pinyin") or "").strip() or None
            traditional = (item.get("traditional") or "").strip() or None
            starred = 1 if item.get("starred") else 0
            note = item.get("note")
            raw = json.dumps(item, ensure_ascii=False)
            existing = _resolve_word_id(db, word, pinyin)
            if existing:
                word_id = existing
                db.execute(
                    """UPDATE words SET pronunciation=COALESCE(?,pronunciation),
                       last_seen=?,raw_json=COALESCE(?,raw_json) WHERE id=?""",
                    (pinyin, now, raw, word_id),
                )
                updated += 1
            else:
                db.execute(
                    """INSERT INTO words(word,meaning,pronunciation,part_of_speech,example,
                       source_url,first_seen,last_seen,raw_json)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (word, None, pinyin, None, "", "hanping", now, now, raw),
                )
                word_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                inserted += 1

            db.execute(
                """INSERT INTO wordbook_words(wordbook_id,word_id,first_seen,last_seen,raw_json)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(wordbook_id,word_id) DO UPDATE SET
                     last_seen=excluded.last_seen,raw_json=excluded.raw_json""",
                (book_id, word_id, now, now, raw),
            )
            db.execute(
                """INSERT INTO hanping_vocab(word_id,traditional,starred,note,record_hash,
                   first_seen,last_seen,raw_json)
                   VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(word_id) DO UPDATE SET
                     traditional=excluded.traditional,
                     starred=excluded.starred,
                     note=excluded.note,
                     record_hash=excluded.record_hash,
                     last_seen=excluded.last_seen,
                     raw_json=excluded.raw_json""",
                (word_id, traditional, starred, note, item["record_hash"], now, now, raw),
            )

            db.execute("DELETE FROM hanping_vocab_tags WHERE word_id=?", (word_id,))
            for tag in sorted(set(item.get("tags") or [])):
                db.execute("INSERT OR IGNORE INTO hanping_tags(name) VALUES(?)", (tag,))
                tag_id = db.execute(
                    "SELECT id FROM hanping_tags WHERE name=?", (tag,)
                ).fetchone()[0]
                db.execute(
                    "INSERT OR IGNORE INTO hanping_vocab_tags(word_id,tag_id) VALUES(?,?)",
                    (word_id, tag_id),
                )

        db.commit()

    return {"inserted": inserted, "updated": updated, "total": len(payload.get("words", []))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path, nargs="?", default=DEFAULT_INPUT)
    args = ap.parse_args()
    stats = sync(args.input.expanduser().resolve())
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
