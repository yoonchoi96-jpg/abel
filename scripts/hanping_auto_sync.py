#!/usr/bin/env python3
"""Automatically discover Hanping exports on a Mac and feed them into Abel.

This is deliberately a local filesystem watcher. It does not log in to
Hanping, inspect browser sessions, decrypt Cloud Backup, or access credentials.

By default it watches iCloud Drive/Downloads, Downloads and Documents and
processes each file once using a content hash. Use --watch for continuous
polling.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "hanping" / ".auto_sync_state.json"
DEFAULT_DIRS = [
    Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Downloads",
    Path.home() / "Downloads",
    Path.home() / "Documents",
]


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_state() -> dict:
    if not STATE.exists():
        return {}
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def candidate_files(directories: list[Path]) -> list[Path]:
    out = []
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            if path.is_file() and path.suffix.lower() in {".json", ".csv", ".tsv", ".txt"}:
                out.append(path)
    return sorted(set(out), key=lambda p: p.stat().st_mtime)


def process(path: Path) -> dict:
    inbox = ROOT / "data" / "hanping"
    normalized = inbox / "normalized.json"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "hanping_vocab_import.py"),
            str(path),
            "-o",
            str(normalized),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "hanping_db_sync.py"),
            str(normalized),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "hanping_router.py"),
            str(normalized),
            "-o",
            str(inbox / "routed.json"),
        ],
        check=True,
    )
    return json.loads((inbox / "routed.json").read_text(encoding="utf-8"))


def run_once(directories: list[Path]) -> int:
    state = load_state()
    processed = 0
    for path in candidate_files(directories):
        digest = file_hash(path)
        key = str(path.resolve())
        if state.get(key) == digest:
            continue
        result = process(path)
        state[key] = digest
        save_state(state)
        print(f"HANPING AUTO-SYNC: {path.name} -> {result['route_counts']}")
        processed += 1
    return processed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("directories", nargs="*", type=Path, default=DEFAULT_DIRS)
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--interval", type=int, default=30)
    args = ap.parse_args()

    while True:
        run_once([p.expanduser().resolve() for p in args.directories])
        if not args.watch:
            return
        time.sleep(max(5, args.interval))


if __name__ == "__main__":
    main()
