#!/usr/bin/env python3
"""
Hanping vocabulary normalizer.

Input:
- JSON exported/saved from Hanping tooling
- TSV/CSV with common Hanping fields
- plain text (one Hanzi item per line)

This module intentionally contains NO login, cookie, OTP, or browser-session handling.
It is the safe ingestion boundary for Hanping -> Abel.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

HANZI_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")

FIELD_ALIASES = {
    "hanzi": {"hanzi", "simplified", "simplified_chinese", "word", "headword", "term", "chinese"},
    "traditional": {"traditional", "traditional_chinese", "trad"},
    "pinyin": {"pinyin", "phonetic", "pronunciation"},
    "note": {"note", "notes", "memo"},
    "starred": {"starred", "star", "is_starred", "favorite", "favourite"},
    "tags": {"tags", "tag", "labels", "categories"},
}

def _norm_key(k: Any) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(k).strip().lower()).strip("_")

def _pick(d: dict[str, Any], logical: str) -> Any:
    aliases = FIELD_ALIASES[logical]
    for k, v in d.items():
        if _norm_key(k) in aliases:
            return v
    return None

def _bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "yes", "y", "starred", "favorite", "favourite"}

def _tags(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        raw = v
    else:
        raw = re.split(r"[,;|]", str(v))
    return sorted({str(x).strip() for x in raw if str(x).strip()})

def _hanzi(s: Any) -> str:
    if s is None:
        return ""
    return "".join(HANZI_RE.findall(str(s)))

def normalize_record(raw: dict[str, Any]) -> dict[str, Any] | None:
    hanzi = _hanzi(_pick(raw, "hanzi"))
    if not hanzi:
        return None
    tags = _tags(_pick(raw, "tags"))
    result = {
        "source": "hanping",
        "hanzi": hanzi,
        "simplified": hanzi,
        "traditional": _pick(raw, "traditional"),
        "pinyin": _pick(raw, "pinyin"),
        "starred": _bool(_pick(raw, "starred")),
        "tags": tags,
        "note": _pick(raw, "note"),
    }
    result["record_hash"] = hashlib.sha256(
        json.dumps(result, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return result

def parse_json(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        for key in ("words", "vocabulary", "vocab", "items", "entries"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            data = [data]
    return [r for x in data if isinstance(x, dict) if (r := normalize_record(x))]

def parse_delimited(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = csv.DictReader(f, dialect="excel-tab" if path.suffix.lower() == ".tsv" else "excel")
        return [r for row in rows if (r := normalize_record(row))]

def parse_text(path: Path) -> list[dict[str, Any]]:
    out = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Strip common bullet/list prefixes but preserve Chinese text.
        line = re.sub(r"^[-*•·\\s]+", "", line)
        h = _hanzi(line)
        if h:
            out.append(normalize_record({"hanzi": h}))
    return [x for x in out if x]

def parse_file(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return parse_json(json.loads(path.read_text(encoding="utf-8-sig")))
    if suffix in {".csv", ".tsv"}:
        return parse_delimited(path)
    return parse_text(path)

def merge(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    # Pinyin distinguishes true homographs. A record without pinyin is
    # incomplete metadata, so it may merge into the only matching Hanzi
    # record, but two explicitly different pinyin values remain separate.
    by_identity: dict[tuple[str, str], dict[str, Any]] = {}
    for r in records:
        word = r["hanzi"]
        pinyin = str(r.get("pinyin") or "").strip()
        exact = (word, pinyin)
        old = by_identity.get(exact)

        if old is None and pinyin:
            old = by_identity.get((word, ""))
            if old is not None:
                del by_identity[(word, "")]
                old["pinyin"] = pinyin

        if old is None and not pinyin:
            explicit = [
                value for (w, p), value in by_identity.items()
                if w == word and p
            ]
            if len(explicit) == 1:
                old = explicit[0]

        if old is None:
            by_identity[exact] = dict(r)
            continue

        old["starred"] = old["starred"] or r["starred"]
        old["tags"] = sorted(set(old["tags"]) | set(r["tags"]))
        old["note"] = old["note"] or r["note"]
        old["traditional"] = old["traditional"] or r["traditional"]
        old["pinyin"] = old["pinyin"] or r["pinyin"]

    for r in by_identity.values():
        r["record_hash"] = hashlib.sha256(
            json.dumps(r, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
    return sorted(
        by_identity.values(),
        key=lambda x: (x["hanzi"], x.get("pinyin") or ""),
    )

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    args = ap.parse_args()

    records = merge(parse_file(args.input))
    payload = {
        "schema_version": 1,
        "source": "hanping",
        "count": len(records),
        "words": records,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)

if __name__ == "__main__":
    main()
