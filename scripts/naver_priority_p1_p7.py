#!/usr/bin/env python3
"""Abel: conservative offline P1-P7 study-priority preview.

Reads only the owner's local saved wordbook checkpoint, and the already
committed Abel HSK 3.0 CSV lists. Never calls Naver or exports private
saved words/IDs to GitHub. Does not overwrite the existing P1-P4 snapshot.

Priority scheme:
P1: >=4 DISTINCT curated wordbooks
P2: 3 curated wordbooks
P3: 2 curated wordbooks
P4: 1 curated wordbook, listed in saved legacy HSK 5 reference
P5: 1 curated wordbook, listed in legacy HSK 6 or HSK 3.0 level 6 NEW list
P6: 1 curated wordbook, listed in HSK 3.0 level 7-9 list
P7: 1 curated wordbook, not matched in those sources (HSK unknown/null)

Reference wordbooks are never counted as a curated save. Matching a term
by headword alone does not prove its sense/pinyin or exam-level edition.
Unknown content shapes remain UNRESOLVED and do not get invented levels.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from naver_wordbook_checkpoint import digest, load_cache
from naver_wordbook_collect import CHECKPOINT, OUTPUT, atomic_save_if_changed
from naver_wordbook_parser import NaverSchemaError, normalize_card, validate_folder_pages


ROOT = Path(__file__).resolve().parents[1]
HSK6_CSV = ROOT / "data/hsk30_level6_1140.csv"
HSK79_CSV = ROOT / "data/hsk30_level7_9_5600.csv"
SCHEMA = "abel.naver.priority.p1-p7.preview.v1"
HSK_REF = re.compile(
    r"^(?:신|新)\s*HSK\s*([56])\s*급\s*필수단어\s*(\d+)\s*탄$",
    flags=re.IGNORECASE,
)


def key(value):
    return unicodedata.normalize("NFKC", value).strip() if isinstance(value, str) else ""


def reference_level(name):
    """Only exact legacy reference list names; never generic study folders."""
    if not isinstance(name, str):
        return None
    cleaned = key(name).replace("_", " ")
    cleaned = " ".join(cleaned.split())
    match = HSK_REF.fullmatch(cleaned)
    return int(match.group(1)) if match else None


def load_hsk_words(path):
    """Preserve the lexical form; reject absent or garbled source files."""
    if not Path(path).is_file():
        raise NaverSchemaError("Required local HSK reference CSV is missing")
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "word" not in reader.fieldnames:
            raise NaverSchemaError("Invalid HSK reference CSV header")
        words = {key(row.get("word")) for row in reader}
    words.discard("")
    if not words:
        raise NaverSchemaError("HSK reference CSV is empty")
    return words


def rank_from_evidence(curated_folder_count, source_levels):
    if curated_folder_count >= 4:
        return "P1", None
    if curated_folder_count == 3:
        return "P2", None
    if curated_folder_count == 2:
        return "P3", None
    if curated_folder_count != 1:
        raise NaverSchemaError("Unrankable word without curated membership")
    for tier, priority in ((5, "P4"), (6, "P5"), (79, "P6")):
        if tier in source_levels:
            return priority, tier
    return "P7", None


def produce(checkpoint, hsk6, hsk79):
    entries = checkpoint.get("entries")
    if not isinstance(entries, dict) or not entries:
        raise NaverSchemaError("Private checkpoint missing wordbook entries")
    words = {}
    legacy = {5: set(), 6: set()}
    folder_levels = {}
    parse_fail = 0
    reference_cards = 0
    total_cards = 0
    curated_card_count = 0

    for folder_id, entry in entries.items():
        if not isinstance(entry, dict):
            raise NaverSchemaError("Invalid private checkpoint entry")
        meta, pages = entry.get("metadata"), entry.get("pages")
        if not isinstance(meta, dict) or meta.get("id") != folder_id:
            raise NaverSchemaError("Invalid checkpoint folder identity")
        if not isinstance(pages, list) or entry.get("digest") != digest(pages):
            raise NaverSchemaError("Checkpoint integrity check failed")
        cards = validate_folder_pages(folder_id, pages, meta.get("wordCount"))
        ref_level = reference_level(meta.get("name"))
        folder_levels[folder_id] = ref_level
        for card in cards:
            total_cards += 1
            if ref_level:
                reference_cards += 1
            try:
                rec = normalize_card(card)
            except NaverSchemaError:
                parse_fail += 1
                continue
            word = key(rec["word"])
            if not word:
                parse_fail += 1
                continue
            if ref_level:
                legacy[ref_level].add(word)
                continue
            curated_card_count += 1
            if word not in words:
                words[word] = {
                    "word": word,
                    "curated_wordbook_ids": set(),
                    "card_ids": set(),
                    "pinyin": "",
                    "definitions": [],
                }
            target = words[word]
            target["curated_wordbook_ids"].add(folder_id)
            target["card_ids"].add(rec["card_id"])
            if rec["pinyin"] and not target["pinyin"]:
                target["pinyin"] = rec["pinyin"]
            for definition in rec["definitions"]:
                if definition not in target["definitions"]:
                    target["definitions"].append(definition)

    results = []
    breakdown = Counter()
    for word, rec in words.items():
        source = set()
        if word in legacy[5]:
            source.add(5)
        if word in legacy[6] or word in hsk6:
            source.add(6)
        if word in hsk79:
            source.add(79)
        count = len(rec["curated_wordbook_ids"])
        priority, level = rank_from_evidence(count, source)
        breakdown[priority] += 1
        results.append({
            "word": word,
            "priority": priority,
            "curated_folder_count": count,
            "curated_wordbook_ids": sorted(rec["curated_wordbook_ids"]),
            "card_ids": sorted(rec["card_ids"]),
            "matched_hsk_level": (
                "5" if level == 5 else "6" if level == 6
                else "7-9" if level == 79 else None
            ),
            "hsk_reference_sources": sorted(
                (["naver_hsk5_legacy"] if 5 in source else [])
                + (["naver_hsk6_legacy_or_hsk30_level6_new"] if 6 in source else [])
                + (["abel_hsk30_level7_9"] if 79 in source else [])
            ),
            "hsk_match_quality": "headword_only" if source else "unmatched",
            "pinyin": rec["pinyin"],
            "definitions": rec["definitions"],
        })

    results.sort(key=lambda item: (item["priority"], item["word"]))
    return {
        "schema_version": SCHEMA,
        "complete": parse_fail == 0,
        "priority_counts_provisional": bool(parse_fail),
        "source_snapshot": "owner_local_checkpoint",
        "classification_basis": "distinct_curated_folders_then_hsk_reference",
        "total_checkpoint_folders": len(entries),
        "reference_folder_count": sum(bool(v) for v in folder_levels.values()),
        "curated_folder_count": sum(v is None for v in folder_levels.values()),
        "saved_card_count": total_cards,
        "reference_card_count": reference_cards,
        "curated_card_count": curated_card_count,
        "unresolved_card_count": parse_fail,
        "distinct_curated_words": len(results),
        "priority_counts": {f"P{i}": breakdown[f"P{i}"] for i in range(1, 8)},
        "priority_criteria": {
            "P1": "four_or_more_curated_folders",
            "P2": "three_curated_folders",
            "P3": "two_curated_folders",
            "P4": "one_curated_folder_and_hsk5_legacy_reference_match",
            "P5": "one_curated_folder_and_hsk6_reference_match",
            "P6": "one_curated_folder_and_hsk30_7_9_match",
            "P7": "one_curated_folder_and_no_confirmed_source_match",
        },
        "limitations": [
            "P4 HSK5 uses only saved legacy Naver numbered lists, not a complete HSK3.0 level5 corpus.",
            "P5 combines legacy HSK6 lists and HSK3.0 level6 NEW words. Edition differences are not resolved.",
            "P6 uses HSK3.0 combined level7-9 list; individual level7,8,9 is not inferred.",
            "Headword-only matching may conflate homographs and polyphonic words.",
            "P7 means unmatched/null, not elementary vocabulary or low importance.",
            "Any unsupported card stays in the private source checkpoint; priority counts are provisional until resolved.",
            "Reference-only words are excluded from curated-study priorities.",
        ],
        "words": results,
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--checkpoint-path", type=Path, default=CHECKPOINT)
    cli.add_argument("--output-dir", type=Path, default=OUTPUT)
    args = cli.parse_args()
    checkpoint = load_cache(args.checkpoint_path)
    result = produce(checkpoint, load_hsk_words(HSK6_CSV), load_hsk_words(HSK79_CSV))
    dest = args.output_dir.expanduser() / "naver_wordbook_priority_p1_p7.json"
    status = args.output_dir.expanduser() / "naver_wordbook_priority_p1_p7_status.json"
    atomic_save_if_changed(dest, result)
    stats = {k:v for k,v in result.items() if k != "words"}
    stats["updated_at"] = datetime.now(timezone.utc).isoformat()
    atomic_save_if_changed(status, stats)
    print("P1-P7 preview: {} curated words / {} unresolved cards".format(
        result["distinct_curated_words"], result["unresolved_card_count"]))
    print("Priority counts: {}".format(result["priority_counts"]))
    print("Local output: {} | status: {}".format(dest, status))
    print("Original verified snapshot is unchanged. No browser/API requests.")


if __name__ == "__main__":
    main()
