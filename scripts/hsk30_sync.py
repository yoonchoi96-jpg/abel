#!/usr/bin/env python3
"""Abel HSK 3.0 vocabulary database synchronizer.

Level 6 is the user's requested 1,140-new-word Korean list.
Levels 7-9 are one combined 5,600-word advanced band.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from naver_wordbook_sync import DB_PATH, init_db, now_iso

ROOT = Path(__file__).resolve().parents[1]
LEVEL6_CSV = ROOT / "data" / "hsk30_level6_1140.csv"
LEVEL79_CSV = ROOT / "data" / "hsk30_level7_9_5600.csv"
EXPORT = ROOT / "data" / "hsk30_wordbooks.json"

BOOKS = [
    ("hsk30:6", "HSK 3.0 6급", LEVEL6_CSV),
    ("hsk30:7-9", "HSK 3.0 7–9급", LEVEL79_CSV),
]

def read_rows(path: Path):
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def upsert_book(db, nid, name, source, now):
    db.execute(
        """INSERT INTO wordbooks(naver_id,name,source_url,first_seen,last_seen,raw_json)
           VALUES(?,?,?,?,?,?)
           ON CONFLICT(naver_id,name) DO UPDATE SET
             source_url=excluded.source_url,last_seen=excluded.last_seen,raw_json=excluded.raw_json""",
        (nid, name, str(source.relative_to(ROOT)), now, now,
         json.dumps({"source": str(source.relative_to(ROOT))}, ensure_ascii=False)),
    )
    return db.execute(
        "SELECT id FROM wordbooks WHERE naver_id=? AND name=?", (nid, name)
    ).fetchone()[0]

def sync():
    init_db()
    now = now_iso()
    stats = {}
    with sqlite3.connect(DB_PATH) as db:
        db.execute("PRAGMA foreign_keys=ON")
        book_ids = {}
        for nid, name, path in BOOKS:
            if not path.exists():
                raise FileNotFoundError(path)
            book_ids[nid] = upsert_book(db, nid, name, path, now)

        for nid, name, path in BOOKS:
            rows = read_rows(path)
            inserted = 0
            for row in rows:
                word = (row.get("word") or "").strip()
                if not word:
                    continue
                meaning = (row.get("meaning_ko") or "").strip() or None
                pronunciation = (row.get("pinyin") or "").strip()
                pos = (row.get("pos") or "").strip()
                source = str(path.relative_to(ROOT))
                raw = json.dumps(row, ensure_ascii=False)

                # Match an existing HSK row by source + word + pinyin when the
                # Korean gloss is not populated yet. This keeps the advanced
                # band idempotent without collapsing homographs.
                row_id = db.execute(
                    """SELECT id FROM words
                       WHERE word=? AND pronunciation=? AND source_url=?
                       ORDER BY id LIMIT 1""",
                    (word, pronunciation, source),
                ).fetchone()
                if row_id:
                    db.execute(
                        """UPDATE words SET
                           meaning=COALESCE(?,meaning),
                           part_of_speech=COALESCE(NULLIF(?,''),part_of_speech),
                           last_seen=?,raw_json=?
                           WHERE id=?""",
                        (meaning, pos, now, raw, row_id[0]),
                    )
                else:
                    db.execute(
                        """INSERT INTO words(word,meaning,pronunciation,part_of_speech,example,
                           source_url,first_seen,last_seen,raw_json)
                           VALUES(?,?,?,?,?,?,?,?,?)""",
                        (word, meaning, pronunciation, pos, "", source, now, now, raw),
                    )
                    row_id = db.execute("SELECT last_insert_rowid()").fetchone()
                if not row_id:
                    continue
                db.execute(
                    """INSERT INTO wordbook_words(wordbook_id,word_id,first_seen,last_seen,raw_json)
                       VALUES(?,?,?,?,?)
                       ON CONFLICT(wordbook_id,word_id) DO UPDATE SET
                         last_seen=excluded.last_seen,raw_json=excluded.raw_json""",
                    (book_ids[nid], row_id[0], now, now, raw),
                )
                inserted += 1
            stats[name] = inserted
        db.commit()

    payload = {
        "schema_version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "collections": [
            {"id": "hsk30:6", "name": "HSK 3.0 6급", "rows": stats.get("HSK 3.0 6급", 0)},
            {"id": "hsk30:7-9", "name": "HSK 3.0 7–9급", "rows": stats.get("HSK 3.0 7–9급", 0)},
        ],
        "source": "Abel curated HSK 3.0 vocabulary sources",
    }
    EXPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))
    print(f"SQLite: {DB_PATH}")
    print(f"Export: {EXPORT}")
    return stats

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sync", action="store_true", required=True)
    ap.parse_args()
    sync()
