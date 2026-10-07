#!/usr/bin/env python3
"""Run the complete local Hanping -> Abel pipeline for one export.

Order is intentional:
1. normalize and deduplicate the export
2. sync user state into the shared canonical DB
3. route the now-canonical records using the DB's HSK/TOCFL/dictionary layers

No login, cookies, browser sessions, cloud decryption, or credentials are used.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "data" / "hanping"
NORMALIZED = INBOX / "normalized.json"
ROUTED = INBOX / "routed.json"


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def sync_export(source: Path) -> dict:
    INBOX.mkdir(parents=True, exist_ok=True)
    run("scripts/hanping_vocab_import.py", str(source), "-o", str(NORMALIZED))
    run("scripts/hanping_db_sync.py", str(NORMALIZED))
    run(
        "scripts/hanping_router.py",
        str(NORMALIZED),
        "-o",
        str(ROUTED),
    )
    return json.loads(ROUTED.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    args = ap.parse_args()
    result = sync_export(args.input.expanduser().resolve())
    print(json.dumps({
        "count": result["count"],
        "route_counts": result["route_counts"],
        "output": str(ROUTED),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
