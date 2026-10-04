#!/usr/bin/env python3
"""Abel HSK 3.0 vocabulary database synchronizer.

Level 6 is the user's requested 1,140-new-word Korean list.
Levels 7-9 are one combined 5,600-word advanced band.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from naver_wordbook_sync import DB_PATH, init_db, now_iso

ROOT = Path(__file__).resolve().parents[1]
LEVEL6_CSV = ROOT / "data" / "hsk30_level6_1140.csv"
LEVEL79_CSV = ROOT / "data" / "hsk30_level7_9_5600.csv"
EXPORT = ROOT / "data" / "hsk30_wordbooks.json"

BOOKS = [
    ("hsk30:6", "HSK 3.0 6급", LEVEL6_CSV),
    ("hsk30:7-9", "HSK 3.0 7–9급", LEVEL79_CSV),
]

def read_rows(path: Path):
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def upsert_book(db, nid, name, source, now):
    db.execute(
        """INSERT INTO wordbooks(naver_id,name,source_url,first_seen,last_seen,raw_json)
           VALUES(?,?,?,?,?,?)
           ON CONFLICT(naver_id,name) DO UPDATE SET
             source_url=excluded.source_url,last_seen=excluded.last_seen,raw_json=excluded.raw_json""",
        (nid, name, str(source.relative_to(ROOT)), now, now,
         json.dumps({"source": str(source.relative_to(ROOT))}, ensure_ascii=False)),
    )
    return db.execute(
        "SELECT id FROM wordbooks WHERE naver_id=? AND name=?", (nid, name)
    ).fetchone()[0]

def sync():
    init_db()
    now = now_iso()
    stats = {}
    with sqlite3.connect(DB_PATH) as db:
        db.execute("PRAGMA foreign_keys=ON")
        book_ids = {}
        for nid, name, path in BOOKS:
            if not path.exists():
                raise FileNotFoundError(path)
            book_ids[nid] = upsert_book(db, nid, name, path, now)

        for nid, name, path in BOOKS:
            rows = read_rows(path)
            inserted = 0
            for row in rows:
                word = (row.get("word") or "").strip()
                if not word:
                    continue
                meaning = (row.get("meaning_ko") or "").strip() or None
                pronunciation = (row.get("pinyin") or "").strip()
                pos = (row.get("pos") or "").strip()
                source = str(path.relative_to(ROOT))
                raw = json.dumps(row, ensure_ascii=False)

                # Match an existing HSK row by source + word + pinyin when the
                # Korean gloss is not populated yet. This keeps the advanced
                # band idempotent without collapsing homographs.
                row_id = db.execute(
                    """SELECT id FROM words
                       WHERE word=? AND pronunciation=? AND source_url=?
                       ORDER BY id LIMIT 1""",
                    (word, pronunciation, source),
                ).fetchone()
                if row_id:
                    db.execute(
                        """UPDATE words SET
                           meaning=COALESCE(?,meaning),
                           part_of_speech=COALESCE(NULLIF(?,''),part_of_speech),
                           last_seen=?,raw_json=?
                           WHERE id=?""",
                        (meaning, pos, now, raw, row_id[0]),
                    )
                else:
                    db.execute(
                        """INSERT INTO words(word,meaning,pronunciation,part_of_speech,example,
                           source_url,first_seen,last_seen,raw_json)
                           VALUES(?,?,?,?,?,?,?,?,?)""",
                        (word, meaning, pronunciation, pos, "", source, now, now, raw),
                    )
                    row_id = db.execute("SELECT last_insert_rowid()").fetchone()
                if not row_id:
                    continue
                db.execute(
                    """INSERT INTO wordbook_words(wordbook_id,word_id,first_seen,last_seen,raw_json)
                       VALUES(?,?,?,?,?)
                       ON CONFLICT(wordbook_id,word_id) DO UPDATE SET
                         last_seen=excluded.last_seen,raw_json=excluded.raw_json""",
                    (book_ids[nid], row_id[0], now, now, raw),
                )
                inserted += 1
            stats[name] = inserted
        db.commit()

    payload = {
        "schema_version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "collections": [
            {"id": "hsk30:6", "name": "HSK 3.0 6급", "rows": stats.get("HSK 3.0 6급", 0)},
            {"id": "hsk30:7-9", "name": "HSK 3.0 7–9급", "rows": stats.get("HSK 3.0 7–9급", 0)},
        ],
        "source": "Abel curated HSK 3.0 vocabulary sources",
    }
    EXPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))
    print(f"SQLite: {DB_PATH}")
    print(f"Export: {EXPORT}")
    return stats

def connect_readonly():
    """Open the SQLite DB read-only; return None when it does not exist."""
    if not Path(DB_PATH).exists():
        return None
    db = sqlite3.connect(f"file:{Path(DB_PATH).resolve().as_posix()}?mode=ro", uri=True)
    db.execute("PRAGMA query_only=ON")
    return db

def safe_read_rows(path: Path):
    """Read CSV rows without raising; returns (rows, error_message)."""
    try:
        return read_rows(path), None
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        return [], str(exc)

def csv_stats(rows):
    keys = set(rows[0].keys()) if rows else set()
    has_trad = "traditional" in keys
    return {
        "total": len(rows),
        "unique": len({((r.get("word") or "").strip(), (r.get("pinyin") or "").strip())
                       for r in rows if (r.get("word") or "").strip()}),
        "has_traditional_column": has_trad,
        "missing_pronunciation": sum(1 for r in rows if not (r.get("pinyin") or "").strip()),
        "missing_korean_gloss": sum(1 for r in rows if not (r.get("meaning_ko") or "").strip()),
        "missing_traditional": sum(
            1 for r in rows if not has_trad or not (r.get("traditional") or "").strip()
        ),
    }

def db_book_count(db, nid):
    if db is None:
        return 0
    try:
        return db.execute(
            """SELECT COUNT(*) FROM wordbook_words ww
               JOIN wordbooks wb ON wb.id=ww.wordbook_id WHERE wb.naver_id=?""",
            (nid,),
        ).fetchone()[0]
    except sqlite3.Error:
        return 0

def db_last_sync(db):
    if db is not None:
        try:
            row = db.execute(
                "SELECT MAX(last_seen) FROM wordbooks WHERE naver_id LIKE 'hsk30:%'"
            ).fetchone()
            if row and row[0]:
                return row[0]
        except sqlite3.Error:
            pass
    try:
        return json.loads(EXPORT.read_text(encoding="utf-8")).get("updated_at")
    except (OSError, ValueError):
        return None

def status():
    db = connect_readonly()
    try:
        result = {}
        for nid, name, path in BOOKS:
            rows, err = safe_read_rows(path)
            st = csv_stats(rows)
            imported = db_book_count(db, nid)
            complete = (
                err is None and imported >= st["unique"] and st["missing_pronunciation"] == 0
                and st["missing_korean_gloss"] == 0 and st["missing_traditional"] == 0
            )
            result[nid] = {
                "name": name,
                "total": st["total"],
                "imported": imported,
                "missing_pronunciation": st["missing_pronunciation"],
                "missing_korean_gloss": st["missing_korean_gloss"],
                "missing_traditional": st["missing_traditional"],
                "status": "OK" if complete else "INCOMPLETE",
            }
        result["last_sync"] = db_last_sync(db)
        result["database"] = str(DB_PATH)
    finally:
        if db is not None:
            db.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result

def validate():
    issues = []
    checks = 0

    def add(severity, code, message, count, nid, samples=None):
        issue = {"severity": severity, "code": code, "message": message,
                 "affected_count": count, "curriculum": nid}
        if samples:
            issue["sample_words"] = samples[:5]
        issues.append(issue)

    db = connect_readonly()
    try:
        for nid, name, path in BOOKS:
            if not path.exists():
                add("ERROR", "FILE_MISSING", f"{path.name} not found", 1, nid)
                continue
            raw = path.read_bytes()
            try:
                raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                add("ERROR", "INVALID_UTF8", f"{path.name} is not valid UTF-8: {exc}", 1, nid)
                continue
            if raw.startswith(b"\xef\xbb\xbf"):
                add("WARNING", "UTF8_BOM", f"{path.name} starts with a UTF-8 BOM", 1, nid)
            rows, err = safe_read_rows(path)
            if err:
                add("ERROR", "CSV_PARSE_ERROR", err, 1, nid)
                continue
            checks += 1
            st = csv_stats(rows)

            for field, col in (("word", "word"), ("pinyin", "pinyin"), ("pos", "pos")):
                bad = [r for r in rows if not (r.get(col) or "").strip()]
                if bad:
                    sev = "ERROR" if field in ("word", "pinyin") else "WARNING"
                    add(sev, f"MISSING_{field.upper()}",
                        f"{len(bad)} rows have an empty {field}", len(bad), nid,
                        [r.get("id", "") for r in bad])

            seen, dups = set(), []
            for r in rows:
                key = ((r.get("word") or "").strip(), (r.get("pinyin") or "").strip())
                if key in seen:
                    dups.append(r.get("id", ""))
                seen.add(key)
            if dups:
                add("WARNING", "DUPLICATE_WORD",
                    "Duplicate word+pinyin within the same source", len(dups), nid, dups)

            if st["missing_traditional"]:
                reason = ("CSV has no traditional column; " if not st["has_traditional_column"] else "")
                add("ERROR", "MISSING_TRADITIONAL",
                    f"{name} {reason}{st['missing_traditional']} words lack traditional form",
                    st["missing_traditional"], nid)
            if st["missing_korean_gloss"]:
                add("WARNING", "EMPTY_KOREAN_GLOSS", "Korean gloss is empty for some words",
                    st["missing_korean_gloss"], nid,
                    [r.get("id", "") for r in rows if not (r.get("meaning_ko") or "").strip()])

            if db is None:
                add("WARNING", "DB_MISSING", f"SQLite database not found: {DB_PATH}", 1, nid)
            else:
                imported = db_book_count(db, nid)
                if imported != st["total"]:
                    add("WARNING", "CSV_SQLITE_MISMATCH",
                        f"CSV has {st['total']} rows but SQLite has {imported}",
                        abs(st["total"] - imported), nid)
    finally:
        if db is not None:
            db.close()

    errors = sum(1 for i in issues if i["severity"] == "ERROR")
    warnings = sum(1 for i in issues if i["severity"] == "WARNING")
    result = {
        "status": "ERRORS" if errors else ("WARNINGS" if warnings else "OK"),
        "issues": issues,
        "summary": {"errors": errors, "warnings": warnings, "ok": max(checks - errors - warnings, 0)},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result

def dry_run():
    db = connect_readonly()
    changes = {"new_wordbooks": 0, "updated_wordbooks": 0, "new_words": 0,
               "updated_words": 0, "skipped_duplicates": 0}
    writes, files_read, counts = 0, 0, []
    try:
        for nid, name, path in BOOKS:
            if not path.exists():
                raise FileNotFoundError(path)
            existing_book = db is not None and db.execute(
                "SELECT 1 FROM wordbooks WHERE naver_id=? AND name=?", (nid, name)
            ).fetchone()
            changes["updated_wordbooks" if existing_book else "new_wordbooks"] += 1
            writes += 1
            rows = read_rows(path)
            files_read += 1
            source = str(path.relative_to(ROOT))
            seen = set()
            n = 0
            for row in rows:
                word = (row.get("word") or "").strip()
                if not word:
                    continue
                pron = (row.get("pinyin") or "").strip()
                if (word, pron) in seen:
                    changes["skipped_duplicates"] += 1
                    continue
                seen.add((word, pron))
                n += 1
                found = None
                if db is not None:
                    try:
                        found = db.execute(
                            """SELECT meaning, part_of_speech FROM words
                               WHERE word=? AND pronunciation=? AND source_url=?
                               ORDER BY id LIMIT 1""",
                            (word, pron, source),
                        ).fetchone()
                    except sqlite3.Error:
                        found = None
                if found is None:
                    changes["new_words"] += 1
                else:
                    meaning = (row.get("meaning_ko") or "").strip() or None
                    pos = (row.get("pos") or "").strip()
                    if (meaning is not None and meaning != found[0]) or (pos and pos != found[1]):
                        changes["updated_words"] += 1
                writes += 2
            counts.append({"id": nid, "name": name, "rows": n})
    finally:
        if db is not None:
            db.close()

    file_changes = []
    try:
        current = json.loads(EXPORT.read_text(encoding="utf-8"))
        current_rows = {c.get("id"): c.get("rows") for c in current.get("collections", [])}
    except (OSError, ValueError):
        current_rows = None
    rel = str(EXPORT.relative_to(ROOT))
    if current_rows is None:
        file_changes.append(f"{rel} (would create)")
    elif any(current_rows.get(c["id"]) != c["rows"] for c in counts):
        file_changes.append(f"{rel} (would update)")
    else:
        file_changes.append(f"{rel} (would update timestamp only)")

    result = {
        "mode": "dry-run",
        "changes": changes,
        "file_changes": file_changes,
        "estimate": {"sqlite_write_operations": writes, "csv_files_read": files_read},
        "warning": "This is a dry-run. No changes were made.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--sync", action="store_true")
    mode.add_argument("--status", action="store_true", help="read-only data status")
    mode.add_argument("--validate", action="store_true", help="read-only integrity checks")
    mode.add_argument("--dry-run", action="store_true", dest="dry_run",
                      help="preview sync without writing")
    args = ap.parse_args()
    if args.status:
        status()
    elif args.validate:
        validate()
    elif args.dry_run:
        dry_run()
    else:
        sync()
