#!/usr/bin/env python3
"""Stage a Hanping vocabulary export for local Abel processing.

This command accepts an official/user-provided Hanping vocabulary export,
normalizes it with the shared importer, and writes the normalized snapshot
outside Git tracking by default.

It intentionally does not authenticate to Hanping or access cloud sessions.
"""
from __future__ import annotations

import argparse
from pathlib import Path

try:
    from scripts.hanping_vocab_import import merge, parse_file
except ModuleNotFoundError:  # direct execution: python scripts/hanping_ingest.py
    from hanping_vocab_import import merge, parse_file


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "hanping" / "normalized.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path, help="Hanping vocabulary export file")
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="normalized JSON destination (default: data/hanping/normalized.json)",
    )
    args = ap.parse_args()

    input_path = args.input.expanduser().resolve()
    if not input_path.is_file():
        raise SystemExit(f"Input file not found: {input_path}")

    records = merge(parse_file(input_path))
    args.output.parent.mkdir(parents=True, exist_ok=True)

    import json

    payload = {
        "schema_version": 1,
        "source": "hanping",
        "input_filename": input_path.name,
        "count": len(records),
        "words": records,
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Input : {input_path}")
    print(f"Words : {len(records)}")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
