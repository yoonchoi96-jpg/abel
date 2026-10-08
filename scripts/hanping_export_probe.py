#!/usr/bin/env python3
"""Inspect a Hanping vocabulary export without importing it.

This probe is intentionally read-only. It reports the actual file shape so
the normalizer can be locked to Hanping's real export format instead of
guessing field names or silently discarding data.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

HANZI_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")


def hanzi_runs(value: Any) -> list[str]:
    return HANZI_RE.findall(str(value or ""))


def inspect_json(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    print("FORMAT: JSON")
    if isinstance(data, dict):
        print("TOP_LEVEL_KEYS:", ", ".join(map(str, data.keys())))
        for key, value in data.items():
            if isinstance(value, list):
                print(f"LIST_FIELD: {key} ({len(value)} items)")
                for i, item in enumerate(value[:3], 1):
                    if isinstance(item, dict):
                        print(f"ITEM_{i}_KEYS:", ", ".join(map(str, item.keys())))
                        print(f"ITEM_{i}_HANZI:", hanzi_runs(item))
                    else:
                        print(f"ITEM_{i}_TYPE:", type(item).__name__)
                break
    elif isinstance(data, list):
        print("TOP_LEVEL_LIST:", len(data))
        for i, item in enumerate(data[:3], 1):
            print(f"ITEM_{i}_TYPE:", type(item).__name__)
            if isinstance(item, dict):
                print(f"ITEM_{i}_KEYS:", ", ".join(map(str, item.keys())))
                print(f"ITEM_{i}_HANZI:", hanzi_runs(item))


def inspect_delimited(path: Path) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(8192)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        reader = csv.DictReader(f, dialect=dialect)
        print("FORMAT: DELIMITED")
        print("DELIMITER:", repr(dialect.delimiter))
        print("HEADERS:", ", ".join(reader.fieldnames or []))
        for i, row in enumerate(reader, 1):
            print(f"ROW_{i}:", json.dumps(row, ensure_ascii=False))
            if i >= 3:
                break


def inspect_text(path: Path) -> None:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    print("FORMAT: TEXT")
    print("LINES:", len(lines))
    nonempty = 0
    chinese = 0
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            continue
        nonempty += 1
        runs = hanzi_runs(stripped)
        if runs:
            chinese += 1
        print(f"LINE_{i}: {stripped!r} HANZI={runs}")
        if nonempty >= 10:
            break
    print("NONEMPTY_LINES_SAMPLE:", nonempty)
    print("CHINESE_LINES_SAMPLE:", chinese)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    args = ap.parse_args()
    path = args.input.expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"Input file not found: {path}")
    print("FILE:", path)
    print("SIZE_BYTES:", path.stat().st_size)
    suffix = path.suffix.lower()
    if suffix == ".json":
        inspect_json(path)
    elif suffix in {".csv", ".tsv"}:
        inspect_delimited(path)
    else:
        inspect_text(path)


if __name__ == "__main__":
    main()
