#!/usr/bin/env python3
"""Local, network-free Abel pipeline validator.

Run on the Mac after pulling the repository. It checks Python syntax,
HSK source counts, local DB presence, export JSON shape, and Drive folders.
"""
from __future__ import annotations

import json
import py_compile
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
DB = HOME / ".naver_wordbook" / "naver_wordbook.sqlite3"
CLASSIFIED = HOME / ".naver_wordbook/exports/abel_classified.json"
EDUCATION = HOME / ".naver_wordbook/exports/abel_gemini_education.json"
DRIVE_CANDIDATES = list((HOME / "Library/CloudStorage").glob("GoogleDrive-*/My Drive/Abel")) if (HOME / "Library/CloudStorage").exists() else []

CHECK_SCRIPTS = [
    ROOT / "scripts/naver_wordbook_sync.py",
    ROOT / "scripts/hsk30_sync.py",
    ROOT / "scripts/abel_daemon.py",
    ROOT / "scripts/abel_drive_bridge.py",
]


def fail(message):
    print(f"[FAIL] {message}")
    return False


def main():
    ok = True

    for path in CHECK_SCRIPTS:
        try:
            py_compile.compile(str(path), doraise=True)
            print(f"[OK] syntax: {path.name}")
        except Exception as exc:
            ok = fail(f"syntax {path.name}: {exc}") and ok

    for filename, expected in [
        ("data/hsk30_level6_1140.csv", 1140),
        ("data/hsk30_level7_9_5600.csv", 5600),
    ]:
        path = ROOT / filename
        if not path.exists():
            ok = fail(f"missing {filename}") and ok
            continue
        lines = sum(1 for _ in path.open(encoding="utf-8")) - 1
        if lines != expected:
            ok = fail(f"{filename}: expected {expected} rows, found {lines}") and ok
        else:
            print(f"[OK] {filename}: {lines} rows")

    if not DB.exists():
        print(f"[WARN] local DB not found: {DB}")
    else:
        try:
            with sqlite3.connect(DB) as db:
                tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                required = {"wordbooks", "words", "wordbook_words", "abel_classifications"}
                missing = required - tables
                if missing:
                    ok = fail(f"DB missing tables: {sorted(missing)}") and ok
                else:
                    words = db.execute("SELECT COUNT(*) FROM words").fetchone()[0]
                    print(f"[OK] DB schema; words={words}")
        except sqlite3.Error as exc:
            ok = fail(f"DB error: {exc}") and ok

    if CLASSIFIED.exists():
        try:
            payload = json.loads(CLASSIFIED.read_text(encoding="utf-8"))
            if payload.get("schema_version") != 1 or not isinstance(payload.get("words"), list):
                ok = fail("abel_classified.json schema invalid") and ok
            else:
                print(f"[OK] classified export: {len(payload['words'])} words")
        except Exception as exc:
            ok = fail(f"classified export invalid: {exc}") and ok
    else:
        print(f"[WARN] classified export not found: {CLASSIFIED}")

    if EDUCATION.exists():
        try:
            payload = json.loads(EDUCATION.read_text(encoding="utf-8"))
            if payload.get("schema_version") != "abel.education.v1" or not isinstance(payload.get("items"), list):
                ok = fail("abel_gemini_education.json schema invalid") and ok
            else:
                print(f"[OK] education export: {len(payload['items'])} items")
        except Exception as exc:
            ok = fail(f"education export invalid: {exc}") and ok
    else:
        print(f"[INFO] education export not created yet")

    if DRIVE_CANDIDATES:
        drive = DRIVE_CANDIDATES[0]
        for name in ("INBOX", "OUTBOX", "ARCHIVE", "FAILED"):
            path = drive / name
            if path.exists():
                print(f"[OK] Drive/{name}")
            else:
                print(f"[INFO] Drive/{name} not created yet")
    else:
        print("[INFO] Google Drive/Abel not detected on this Mac")

    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
