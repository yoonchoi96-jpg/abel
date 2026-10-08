#!/usr/bin/env python3
"""Route normalized Hanping records to Abel's canonical learning layers.

Routing is deterministic and read-only with respect to the vocabulary payload:
the shared SQLite DB is consulted for existing HSK/TOCFL/dictionary identity,
then each record receives a route label. No account, browser, cookie or cloud
access is performed here.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

try:
    from scripts import abel_wordbook_db as db_layer
except ModuleNotFoundError:
    import abel_wordbook_db as db_layer

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "hanping" / "normalized.json"
DEFAULT_OUTPUT = ROOT / "data" / "hanping" / "routed.json"


def _wordbook_names(db: sqlite3.Connection, word_id: int) -> set[str]:
    rows = db.execute(
        """SELECT wb.name
           FROM wordbook_words wbw
           JOIN wordbooks wb ON wb.id = wbw.wordbook_id
           WHERE wbw.word_id=?""",
        (word_id,),
    ).fetchall()
    return {str(r[0]) for r in rows}


def _route_for(
    db: sqlite3.Connection, word: str, pinyin: str | None, tags: list[str]
) -> tuple[str, int | None]:
    candidates = []
    if pinyin:
        candidates = db.execute(
            "SELECT id FROM words WHERE word=? AND pronunciation=? ORDER BY id",
            (word, pinyin),
        ).fetchall()

    if not candidates:
        candidates = db.execute(
            "SELECT id FROM words WHERE word=? ORDER BY id",
            (word,),
        ).fetchall()

    hsk6_tags = {"hsk6", "hsK6".lower(), "신hsk 6급", "hsk 6급", "level 6"}
    hsk79_tags = {
        "hsk7", "hsk8", "hsk9", "hsk 7-9", "hsk 7~9",
        "신hsk 7-9급", "level 7-9", "level 7–9",
    }
    tocfl_tags = {"tocfl", "tocfl a", "tocfl b", "tocfl c"}

    lowered = {str(t).strip().lower() for t in tags}

    for row in candidates:
        word_id = row[0]
        books = {x.strip().lower() for x in _wordbook_names(db, word_id)}
        if any("6급" in b and "hsk" in b for b in books) or lowered & hsk6_tags:
            return "hsk30_level6", word_id
        if (
            any(
                ("7" in b or "8" in b or "9" in b) and "hsk" in b
                for b in books
            )
            or lowered & hsk79_tags
        ):
            return "hsk30_level7_9", word_id
        if any("tocfl" in b for b in books) or lowered & tocfl_tags:
            return "tocfl", word_id

    if candidates:
        return "existing", candidates[0][0]
    return "new", None


def route_payload(input_path: Path, db_path: Path) -> dict:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or payload.get("source") != "hanping":
        raise ValueError("unsupported Hanping normalized payload")

    db_layer.DB_PATH = db_path
    db_layer.init_db()

    counts: dict[str, int] = {}
    routed = []

    with sqlite3.connect(db_path) as db:
        for item in payload.get("words", []):
            word = (item.get("hanzi") or item.get("simplified") or "").strip()
            if not word:
                continue
            route, word_id = _route_for(
                db, word, (item.get("pinyin") or "").strip() or None, item.get("tags") or []
            )
            out = dict(item)
            out["route"] = route
            out["canonical_word_id"] = word_id
            routed.append(out)
            counts[route] = counts.get(route, 0) + 1

    return {
        "schema_version": 1,
        "source": "hanping",
        "count": len(routed),
        "route_counts": counts,
        "words": routed,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path, nargs="?", default=DEFAULT_INPUT)
    ap.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--db", type=Path, default=db_layer.DB_PATH)
    args = ap.parse_args()

    result = route_payload(
        args.input.expanduser().resolve(),
        args.db.expanduser().resolve(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["route_counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
