#!/usr/bin/env python3
"""Abel local daemon: Naver SQLite -> deterministic HSK 3.0 classification -> local export.

No AI/API calls are used. Naver browser sync is optional at runtime.
"""
from __future__ import annotations

import argparse
import csv
import fcntl
import json
import os
import sqlite3
import subprocess
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = Path.home() / ".naver_wordbook" / "naver_wordbook.sqlite3"
OUT = Path.home() / ".naver_wordbook" / "exports" / "abel_classified.json"
HSK_CACHE = Path.home() / ".naver_wordbook" / "cache" / "hsk30_match_cache.json"
LOCK = Path.home() / ".naver_wordbook" / ".abel_daemon.lock"

POLL_SECONDS = 3
DEBOUNCE_SECONDS = 8
NAVER_SYNC_INTERVAL = 300
GIT_SYNC_INTERVAL = 600
PUSH_EXPORT = False
PYTHON_BIN = os.environ.get("ABEL_PYTHON", "python3")


def now():
    return datetime.now(timezone.utc).isoformat()


def normalize_word(value):
    return unicodedata.normalize("NFKC", (value or "").strip())


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


def load_hsk_index():
    """Cache the normalized HSK index until either CSV changes."""
    files = [
        (ROOT / "data" / "hsk30_level6_1140.csv", "HSK 3.0 6급"),
        (ROOT / "data" / "hsk30_level7_9_5600.csv", "HSK 3.0 7–9급"),
    ]
    signature = {
        str(path): path.stat().st_mtime_ns
        for path, _ in files
        if path.exists()
    }

    HSK_CACHE.parent.mkdir(parents=True, exist_ok=True)
    try:
        cached = json.loads(HSK_CACHE.read_text(encoding="utf-8"))
        if cached.get("signature") == signature and isinstance(cached.get("index"), dict):
            return cached["index"]
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass

    index = {}
    for path, band in files:
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                word = normalize_word(row.get("word"))
                if not word:
                    continue
                index.setdefault(word, []).append({
                    "band": band,
                    "meaning_ko": (row.get("meaning_ko") or "").strip(),
                    "pinyin": (row.get("pinyin") or "").strip(),
                    "pos": (row.get("pos") or "").strip(),
                })

    tmp = HSK_CACHE.with_suffix(".tmp")
    tmp.write_text(
        json.dumps({"signature": signature, "index": index}, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp.replace(HSK_CACHE)
    return index


def choose_hsk_candidate(candidates):
    if not candidates:
        return None
    bands = {item["band"] for item in candidates}
    if len(bands) == 1:
        return candidates[0]
    return {
        "band": "HSK 3.0 중복·검토",
        "meaning_ko": "",
        "pinyin": "",
        "pos": "",
    }


def classify_and_export():
    with sqlite3.connect(DB) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        ensure_schema(db)
        hsk = load_hsk_index()

        user_rows = db.execute("""
            SELECT DISTINCT w.id, w.word
            FROM words w
            JOIN wordbook_words ww ON ww.word_id = w.id
            JOIN wordbooks wb ON wb.id = ww.wordbook_id
            WHERE wb.name NOT LIKE 'HSK 3.0 %'
        """).fetchall()

        for row in user_rows:
            candidates = hsk.get(normalize_word(row["word"]), [])
            selected = choose_hsk_candidate(candidates)
            band = selected["band"] if selected else None
            db.execute("""
                INSERT INTO abel_classifications(word_id,hsk_band,hsk_word,matched_at)
                VALUES(?,?,?,?)
                ON CONFLICT(word_id) DO UPDATE SET
                  hsk_band=excluded.hsk_band,
                  hsk_word=excluded.hsk_word,
                  matched_at=excluded.matched_at
            """, (row["id"], band, row["word"], now()))

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
                    "id": row["id"],
                    "word": row["word"],
                    "meaning": row["meaning"],
                    "pronunciation": row["pronunciation"],
                    "part_of_speech": row["part_of_speech"],
                    "example": row["example"],
                    "wordbooks": (row["wordbooks"] or "").split(",") if row["wordbooks"] else [],
                    "hsk_band": row["hsk_band"],
                }
                for row in rows
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
    for attempt in range(1, 4):
        try:
            process = subprocess.run(
                [PYTHON_BIN, str(script), "--sync"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=240,
            )
            print(process.stdout[-4000:], end="", flush=True)
            if process.returncode == 0:
                return True
            print(f"[naver] sync failed attempt {attempt}: {process.stderr[-2000:]}", flush=True)
        except Exception as exc:
            print(f"[naver] sync exception attempt {attempt}: {exc}", flush=True)
        if attempt < 3:
            time.sleep(5 * attempt)
    return False


def git_sync():
    if not PUSH_EXPORT:
        return
    try:
        subprocess.run(["git", "add", str(OUT)], cwd=ROOT, check=True, timeout=30)
        changed = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=ROOT, timeout=30
        ).returncode != 0
        if not changed:
            return
        subprocess.run(
            ["git", "commit", "-m", "chore: sync local Naver wordbook classification"],
            cwd=ROOT, check=True, timeout=30
        )
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=ROOT, check=True, timeout=120)
        subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True, timeout=120)
        print("[git] export pushed", flush=True)
    except Exception as exc:
        print("[git] sync skipped/failed: " + str(exc), flush=True)


def acquire_lock():
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    handle = LOCK.open("w", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise SystemExit("Another Abel daemon is already running")
    handle.write(str(os.getpid()))
    handle.flush()
    return handle


def main():
    parser = argparse.ArgumentParser(description="Abel local Naver/HSK daemon")
    parser.add_argument("--once", action="store_true", help="sync once, classify, export, then exit")
    parser.add_argument("--no-browser", action="store_true", help="skip authenticated Naver browser sync")
    args = parser.parse_args()

    DB.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = acquire_lock()
    try:
        print(f"Abel daemon watching: {DB}")
        print(f"Local classified export: {OUT}")
        print("API calls: 0")

        if args.once:
            if not args.no_browser:
                run_naver_sync()
            count, _ = classify_and_export()
            print(f"[once] classified/exported {count} words", flush=True)
            return

        pending_since = None
        last_version = None
        last_naver_sync = 0.0
        last_git_sync = 0.0

        while True:
            if time.monotonic() - last_naver_sync >= NAVER_SYNC_INTERVAL:
                if run_naver_sync():
                    last_naver_sync = time.monotonic()
                    pending_since = time.monotonic()

            if time.monotonic() - last_git_sync >= GIT_SYNC_INTERVAL:
                git_sync()
                last_git_sync = time.monotonic()

            try:
                version = data_version()
            except sqlite3.Error as exc:
                print(f"[db] {exc}", flush=True)
                time.sleep(POLL_SECONDS)
                continue

            if last_version is None:
                last_version = version
                count, _ = classify_and_export()
                print(f"[init] classified/exported {count} words", flush=True)
            elif version != last_version:
                last_version = version
                pending_since = time.monotonic()
                print("[change] SQLite changed; debounce started", flush=True)
            elif pending_since is not None and time.monotonic() - pending_since >= DEBOUNCE_SECONDS:
                count, _ = classify_and_export()
                print(f"[sync] classified/exported {count} words", flush=True)
                pending_since = None

            time.sleep(POLL_SECONDS)
    finally:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        lock_handle.close()


if __name__ == "__main__":
    main()
