#!/usr/bin/env python3
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import abel_wordbook_db as db
from scripts.hanping_router import route_payload


class HanpingRouterTest(unittest.TestCase):
    def test_routes_existing_hsk_and_new_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db.DB_PATH = root / "abel.sqlite3"
            db.init_db()
            now = db.now_iso()
            with sqlite3.connect(db.DB_PATH) as conn:
                conn.execute(
                    """INSERT INTO wordbooks
                       (name, first_seen, last_seen) VALUES (?,?,?)""",
                    ("신HSK 6급", now, now),
                )
                book_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.execute(
                    """INSERT INTO words
                       (word, meaning, pronunciation, first_seen, last_seen)
                       VALUES (?,?,?,?,?)""",
                    ("维护", "유지하다", "wei2 hu4", now, now),
                )
                word_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.execute(
                    """INSERT INTO wordbook_words
                       (wordbook_id, word_id, first_seen, last_seen)
                       VALUES (?,?,?,?)""",
                    (book_id, word_id, now, now),
                )
                conn.commit()

            source = root / "normalized.json"
            source.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source": "hanping",
                        "words": [
                            {"hanzi": "维护", "pinyin": "wei2 hu4", "tags": []},
                            {"hanzi": "你好", "pinyin": "ni3 hao3", "tags": []},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            result = route_payload(source, db.DB_PATH)
            self.assertEqual(result["route_counts"]["hsk30_level6"], 1)
            self.assertEqual(result["route_counts"]["new"], 1)


if __name__ == "__main__":
    unittest.main()
