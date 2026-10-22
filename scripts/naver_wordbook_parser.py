#!/usr/bin/env python3
"""Offline parser for Naver Chinese personal wordbook JSON; NO account/network access.

For locally captured JSON values only. Never interpret diagnostic metadata as
actual cards, and never report a partial collection as complete.
"""
from __future__ import annotations

import html
import json
import re
import unicodedata
from html.parser import HTMLParser

HANZI = re.compile(r"[\u3400-\u9fff]")
PINYIN_KEYS = ("pinyin", "pin_yin", "pinyin_text", "pinyinText", "romanization")


class NaverSchemaError(ValueError):
    pass


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def clean_text(value):
    if not isinstance(value, str):
        return ""
    value = html.unescape(value)
    if re.search(r"<[A-Za-z][A-Za-z0-9]*(?:\s|>|/)", value):
        p = _PlainText()
        p.feed(value)
        value = " ".join(p.parts)
    return " ".join(value.split())


def string_from(record, *keys):
    if not isinstance(record, dict):
        return ""
    for key in keys:
        val = clean_text(record.get(key))
        if val:
            return val
    return ""


def _entry_from_content(content):
    if not isinstance(content, str):
        raise NaverSchemaError("card.content must be a JSON-encoded string")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise NaverSchemaError("card.content is not JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("entry"), dict):
        raise NaverSchemaError("card.content missing entry object")
    return payload["entry"]


def normalize_card(card):
    """Preserve the folder/card identity; never invent a meaning or pinyin."""
    if not isinstance(card, dict):
        raise NaverSchemaError("card must be an object")
    folder_id = string_from(card, "wordbookId")
    card_id = string_from(card, "id")
    if not folder_id or not card_id:
        raise NaverSchemaError("card missing wordbookId or id")
    entry = _entry_from_content(card.get("content"))
    members = entry.get("members")
    meanings = entry.get("means")
    if not isinstance(members, list) or not isinstance(meanings, list):
        raise NaverSchemaError("entry.members or entry.means missing")
    names = [string_from(m, "entry_name") for m in members if isinstance(m, dict)]
    names = [x for x in names if x]
    headword = next((x for x in names if HANZI.search(x)), "") or string_from(card, "name")
    if not headword:
        raise NaverSchemaError("no headword in card")
    definitions = []
    for meaning in meanings:
        if not isinstance(meaning, dict):
            raise NaverSchemaError("entry.means contains a nonobject")
        gloss = string_from(meaning, "show_mean")
        if gloss:
            definitions.append({
                "meaning": gloss,
                "part_of_speech": string_from(meaning, "part_name"),
                "language": string_from(meaning, "language"),
            })
    pronunciations = []
    for member in members:
        if not isinstance(member, dict):
            raise NaverSchemaError("entry.members contains a nonobject")
        prons = member.get("prons", [])
        if not isinstance(prons, list):
            raise NaverSchemaError("entry.members.prons must be a list")
        for pron in prons:
            if not isinstance(pron, dict):
                raise NaverSchemaError("pronunciation must be an object")
            # The nested keys were not identified by the diagnostic.
            # Extract ONLY explicitly named pinyin fields.
            value = string_from(pron, *PINYIN_KEYS)
            if value:
                pronunciations.append(value)
    # mix_pron is preserved unclassified; do not silently call it pinyin.
    return {
        "card_id": card_id,
        "entry_id": string_from(card, "entryId"),
        "wordbook_id": folder_id,
        "word": unicodedata.normalize("NFKC", headword),
        "raw_member_names": names,
        "definitions": definitions,
        "pinyin": pronunciations[0] if pronunciations else "",
        "mix_pron_unverified": string_from(entry, "mix_pron"),
        "missing_pinyin": not bool(pronunciations),
        "missing_meaning": not bool(definitions),
        "read": card.get("read") if isinstance(card.get("read"), bool) else None,
        "create_date": card.get("createDate"),
    }


def classify_cards(cards):
    """Count UNIQUE folder IDs per Chinese word, never same-folder duplicates."""
    if not isinstance(cards, list):
        raise NaverSchemaError("cards must be a list")
    normalized = [normalize_card(card) for card in cards]
    grouped = {}
    for rec in normalized:
        word = rec["word"]
        if word not in grouped:
            grouped[word] = {
                "word": word, "wordbook_ids": set(),
                "card_ids": set(), "definitions": [],
                "pinyin": "", "missing_pinyin": True,
            }
        agg = grouped[word]
        agg["wordbook_ids"].add(rec["wordbook_id"])
        agg["card_ids"].add(rec["card_id"])
        if not agg["pinyin"] and rec["pinyin"]:
            agg["pinyin"] = rec["pinyin"]
            agg["missing_pinyin"] = False
        for definition in rec["definitions"]:
            if definition not in agg["definitions"]:
                agg["definitions"].append(definition)
    result = []
    for agg in grouped.values():
        n = len(agg["wordbook_ids"])
        result.append({
            "word": agg["word"], "pinyin": agg["pinyin"],
            "definitions": agg["definitions"],
            "wordbook_ids": sorted(agg["wordbook_ids"]),
            "card_ids": sorted(agg["card_ids"]),
            "folder_count": n, "priority": "P" + str(5 - min(n, 4)),
            "missing_pinyin": agg["missing_pinyin"],
            "missing_meaning": not bool(agg["definitions"]),
        })
    return sorted(result, key=lambda x: (x["priority"], x["word"]))


def validate_folder_pages(folder_id, pages, expected_total):
    """Require all pages, no duplicate cards, and matching reported count."""
    if not isinstance(pages, list) or not pages:
        raise NaverSchemaError("no pages for folder")
    if not isinstance(expected_total, int) or isinstance(expected_total, bool) or expected_total < 0:
        raise NaverSchemaError("invalid expected count")
    all_cards = []
    reported_page_total = None
    returned_pages = set()
    for raw in pages:
        data = raw.get("data") if isinstance(raw, dict) else None
        if not isinstance(data, dict) or not isinstance(data.get("m_items"), list):
            raise NaverSchemaError("invalid page data.m_items")
        total = data.get("m_total")
        count = data.get("m_total_pages")
        number = data.get("m_current_page")
        if (not isinstance(total, int) or total != expected_total
                or not isinstance(count, int) or count < 0
                or not isinstance(number, int) or number < 0):
            raise NaverSchemaError("invalid/inconsistent page metadata")
        if reported_page_total is None:
            reported_page_total = count
        if reported_page_total != count or number in returned_pages:
            raise NaverSchemaError("page count changed or page repeated")
        returned_pages.add(number)
        for card in data["m_items"]:
            if not isinstance(card, dict) or card.get("wordbookId") != folder_id:
                raise NaverSchemaError("card folder ID does not match page")
            all_cards.append(card)
    if reported_page_total == 0:
        # Some backends emit a single empty page for empty wordbooks.
        valid_page_numbers = [{0}, {1}] if expected_total == 0 else []
    else:
        valid_page_numbers = [
            set(range(reported_page_total)),
            set(range(1, reported_page_total + 1)),
        ]
    if (returned_pages not in valid_page_numbers
            or len(all_cards) != expected_total):
        raise NaverSchemaError("missing/noncontiguous pages or card-count mismatch")
    seen_cards = [x.get("id") for x in all_cards]
    if None in seen_cards or len(set(seen_cards)) != len(seen_cards):
        raise NaverSchemaError("missing or repeated card ID")
    return all_cards


def build_snapshot(folders, per_folder_pages, *, reported_folder_count):
    """Build only when both folder index and every card page are verified."""
    if not isinstance(folders, list) or not folders:
        raise NaverSchemaError("no wordbooks")
    if (not isinstance(reported_folder_count, int)
            or isinstance(reported_folder_count, bool)
            or len(folders) != reported_folder_count):
        raise NaverSchemaError("wordbook list is incomplete or unverified")
    if not isinstance(per_folder_pages, dict):
        raise NaverSchemaError("folder pages must be a dictionary")
    folder_ids = []
    cards = []
    for folder in folders:
        if not isinstance(folder, dict):
            raise NaverSchemaError("invalid folder")
        folder_id = string_from(folder, "id")
        if not folder_id or not string_from(folder, "name"):
            raise NaverSchemaError("missing folder ID/name")
        if folder_id in folder_ids:
            raise NaverSchemaError("duplicate folder ID")
        folder_ids.append(folder_id)
        cards.extend(validate_folder_pages(
            folder_id, per_folder_pages.get(folder_id), folder.get("wordCount")))
    if set(per_folder_pages) != set(folder_ids):
        raise NaverSchemaError("unexpected/incomplete folder keys")
    return {
        "schema_version": "abel.naver.wordbooks.preview.v1",
        "verified_card_pages": True,
        "verified_folder_count": reported_folder_count,
        "folder_count": len(folder_ids),
        "saved_card_count": len(cards),
        "words": classify_cards(cards),
    }
