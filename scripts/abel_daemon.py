#!/usr/bin/env python3
"""Abel local daemon: watch Naver SQLite, classify new words against HSK 3.0, and export a local JSON snapshot.

No network/API is used. Naver credentials and personal wordbook contents stay on the Mac.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = Path.home() / ".naver_wordbook" / "naver_wordbook.sqlite3"
OUT = Path.home() / ".naver_wordbook" / "exports" / "abel_classified.json"
POLL_SECONDS = 3
DEBOUNCE_SECONDS = 8
NAVER_SYNC_INTERVAL = 300  # seconds; browser sync, no AI/API calls
LOCK = Path.home() / ".naver_wordbook" / ".abel_daemon.lock"

def now():
    return datetime.now(timezone.utc).isoformat()

def ensure_schema(db):
    db.execute("""CREATE TABLE IF NOT EXISTS abel_classifications (
        word_id INTEGER PRIMARY KEY,
        hsk_band TEXT,
        hsk_word TEXT,
        matched_at TEXT NOT NULL,
        FOREIGN KEY(word_id) REFERENCES words(id)
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_abel_class_hsk ON abel_classifications(hsk_band)")
    db.commit()

def classify_and_export():
    with sqlite3.connect(DB) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        ensure_schema(db)
        # Exact Chinese-word matching is deterministic and API-free.
        db.execute("""
            INSERT INTO abel_classifications(word_id,hsk_band,hsk_word,matched_at)
            SELECT w.id,
                   CASE
                     WHEN EXISTS (
                       SELECT 1 FROM wordbook_words ww
                       JOIN wordbooks wb ON wb.id=ww.wordbook_id
                       WHERE ww.word_id=w.id AND wb.name='HSK 3.0 7–9급'
                     ) THEN 'HSK 3.0 7–9급'
                     WHEN EXISTS (
                       SELECT 1 FROM wordbook_words ww
                       JOIN wordbooks wb ON wb.id=ww.wordbook_id
                       WHERE ww.word_id=w.id AND wb.name='HSK 3.0 6급'
                     ) THEN 'HSK 3.0 6급'
                     ELSE NULL
                   END,
                   w.word,
                   ? 
            FROM words w
            WHERE EXISTS (
              SELECT 1 FROM wordbook_words ww
              JOIN wordbooks wb ON wb.id=ww.wordbook_id
              WHERE ww.word_id=w.id
                AND wb.name NOT LIKE 'HSK 3.0 %'
            )
            ON CONFLICT(word_id) DO UPDATE SET
              hsk_band=excluded.hsk_band,
              hsk_word=excluded.hsk_word,
              matched_at=excluded.matched_at
        """, (now(),))

        rows = db.execute("""
            SELECT w.id,w.word,w.meaning,w.pronunciation,w.part_of_speech,w.example,
                   GROUP_CONCAT(DISTINCT wb.name) AS wordbooks,
                   COALESCE(ac.hsk_band,'미매칭') AS hsk_band
            FROM words w
            JOIN wordbook_words ww ON ww.word_id=w.id
            JOIN wordbooks wb ON wb.id=ww.wordbook_id
            LEFT JOIN abel_classifications ac ON ac.word_id=w.id
            WHERE wb.name NOT LIKE 'HSK 3.0 %'
            GROUP BY w.id
            ORDER BY w.word COLLATE NOCASE
        """).fetchall()

        payload = {
            "schema_version": 1,
            "updated_at": now(),
            "source": "local Naver Wordbook SQLite",
            "api_calls": 0,
            "count": len(rows),
            "words": [
                {
                    "id": r["id"], "word": r["word"], "meaning": r["meaning"],
                    "pronunciation": r["pronunciation"], "part_of_speech": r["part_of_speech"],
                    "example": r["example"],
                    "wordbooks": (r["wordbooks"] or "").split(",") if r["wordbooks"] else [],
                    "hsk_band": r["hsk_band"],
                } for r in rows
            ],
        }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(OUT)
    return len(rows), payload

def data_version():
    with sqlite3.connect(DB) as db:
        return db.execute("PRAGMA data_version").fetchone()[0]

def run_naver_sync():
    script = ROOT / "scripts" / "naver_wordbook_sync.py"
    try:
        p = subprocess.run(
            ["python3", str(script), "--sync"],
            cwd=ROOT, text=True, capture_output=True, timeout=240,
        )
        print(p.stdout[-4000:], end="", flush=True)
        if p.returncode != 0:
            print("[naver] sync failed: " + p.stderr[-2000:], flush=True)
        return p.returncode == 0
    except Exception as e:
        print("[naver] sync exception: " + str(e), flush=True)
        return False

def main():
    DB.parent.mkdir(parents=True, exist_ok=True)
    try:
        LOCK.write_text(str(__import__("os").getpid()), encoding="utf-8")
    except Exception:
        pass
    print(f"Abel daemon watching: {DB}")
    print(f"Local classified export: {OUT}")
    print("API calls: 0")
    pending_since = None
    last_version = None
    last_naver_sync = 0.0
    try:
        while True:
            if time.monotonic() - last_naver_sync >= NAVER_SYNC_INTERVAL:
                if run_naver_sync():
                    last_naver_sync = time.monotonic()
                    pending_since = time.monotonic()
            try:
                version = data_version()
            except sqlite3.Error as e:
                print(f"[db] {e}", flush=True)
                time.sleep(POLL_SECONDS)
                continue
            if last_version is None:
                last_version = version
                n,_ = classify_and_export()
                print(f"[init] classified/exported {n} words", flush=True)
            elif version != last_version:
                last_version = version
                pending_since = time.monotonic()
                print("[change] SQLite changed; debounce started", flush=True)
            elif pending_since is not None and time.monotonic() - pending_since >= DEBOUNCE_SECONDS:
                n,_ = classify_and_export()
                print(f"[sync] classified/exported {n} words", flush=True)
                pending_since = None
            time.sleep(POLL_SECONDS)
    finally:
        try: LOCK.unlink()
        except FileNotFoundError: pass

if __name__ == "__main__":
    main()
