#!/usr/bin/env python3
"""
Abel - Naver Dictionary personal wordbook synchronizer.

Authenticated Naver session stays on the user's Mac. Abel never stores the
Naver password. The collector discovers wordbooks, preserves memberships,
deduplicates words globally, and keeps raw probe snapshots for diagnostics.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

DEFAULT_URL = "https://learn.dict.naver.com/wordbook/enkodict/#/my/main"
DATA_ROOT = Path(os.environ.get("NAVER_WORDBOOK_DATA", "~/.naver_wordbook")).expanduser()
PROFILE_DIR = DATA_ROOT / "browser_profile"
EXPORT_DIR = DATA_ROOT / "exports"
DB_PATH = DATA_ROOT / "naver_wordbook.sqlite3"
REPO_EXPORT = Path(os.environ.get("NAVER_WORDBOOK_EXPORT", "data/naver_wordbook.json"))

NETWORK_HINTS = ("wordbook", "dict.naver", "learn.dict")
MAX_RESPONSE = 2_000_000

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def ensure_dirs() -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPO_EXPORT.parent.mkdir(parents=True, exist_ok=True)

def init_db() -> None:
    with sqlite3.connect(DB_PATH) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS wordbooks (
            id INTEGER PRIMARY KEY,
            naver_id TEXT,
            name TEXT NOT NULL,
            source_url TEXT,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            raw_json TEXT,
            UNIQUE(naver_id, name)
        );
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY,
            word TEXT NOT NULL,
            meaning TEXT,
            pronunciation TEXT,
            part_of_speech TEXT,
            example TEXT,
            source_url TEXT,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            raw_json TEXT,
            UNIQUE(word, meaning)
        );
        CREATE TABLE IF NOT EXISTS wordbook_words (
            wordbook_id INTEGER NOT NULL,
            word_id INTEGER NOT NULL,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            raw_json TEXT,
            PRIMARY KEY(wordbook_id, word_id),
            FOREIGN KEY(wordbook_id) REFERENCES wordbooks(id),
            FOREIGN KEY(word_id) REFERENCES words(id)
        );
        CREATE INDEX IF NOT EXISTS idx_wordbook_words_word ON wordbook_words(word_id);
        CREATE INDEX IF NOT EXISTS idx_wordbook_words_wordbook ON wordbook_words(wordbook_id);
        """)
        db.commit()

def lines(text: str) -> list[str]:
    return [x.strip() for x in re.split(r"\n+", text or "") if x.strip()]

def safe_json(value):
    try:
        return json.loads(value)
    except Exception:
        return None

def capture_network(page):
    events = []
    def on_response(response):
        url = response.url
        if not any(h in url.lower() for h in NETWORK_HINTS):
            return
        try:
            ctype = (response.headers.get("content-type") or "").lower()
            if not any(x in ctype for x in ("json", "javascript", "text", "xml")):
                return
            body = response.body()
            truncated = len(body) > MAX_RESPONSE
            if truncated:
                body = body[:MAX_RESPONSE]
            events.append({
                "url": url, "status": response.status, "content_type": ctype,
                "truncated": truncated,
                "body": body.decode("utf-8", errors="replace"),
            })
        except Exception as exc:
            events.append({"url": url, "error": repr(exc)})
    page.on("response", on_response)
    return events

def visible_text(el):
    try:
        return (el.inner_text(timeout=700) or "").strip()
    except Exception:
        return ""

def attr(el, name):
    try:
        return el.get_attribute(name) or ""
    except Exception:
        return ""

def discover_wordbooks(page) -> list[dict]:
    """
    Best-effort discovery from links/buttons/ARIA labels and hrefs.
    The raw DOM is retained in probe snapshots, so selectors can be tightened
    after the first real Naver session.
    """
    found = {}
    selectors = [
        "a[href*='wordbook']", "a[href*='#/my/']",
        "[role='link']", "button", "[role='button']",
        "li", "[class*='wordbook']", "[class*='Wordbook']",
    ]
    for selector in selectors:
        try:
            loc = page.locator(selector)
            for i in range(min(loc.count(), 3000)):
                el = loc.nth(i)
                if not el.is_visible():
                    continue
                text = visible_text(el)
                href = attr(el, "href")
                aria = attr(el, "aria-label")
                title = attr(el, "title")
                data_id = ""
                for a in ("data-id", "data-wordbook-id", "data-wordbookid", "data-book-id"):
                    data_id = attr(el, a)
                    if data_id:
                        break
                label = (text or aria or title).strip()
                if not label or len(label) > 200:
                    continue
                if not (href or data_id or "단어장" in label or "HSK" in label.upper() or "여행" in label):
                    continue
                if label.lower() in {"로그인", "회원가입", "검색", "닫기", "메뉴"}:
                    continue
                key = f"{href}|{data_id}|{label}"
                found[key] = {
                    "naver_id": data_id,
                    "name": label,
                    "href": href,
                    "source_url": urljoin(page.url, href) if href else page.url,
                    "raw_text": text,
                }
        except Exception:
            continue

    # Prefer items whose href/label actually looks like a wordbook.
    candidates = []
    for item in found.values():
        blob = " ".join(str(item.get(k, "")) for k in ("href", "name", "raw_text")).lower()
        if "wordbook" in blob or "#/my/" in blob or "단어장" in blob or "hsk" in blob:
            candidates.append(item)

    # Always retain the main page as a fallback pseudo-wordbook.
    if not candidates:
        candidates = [{
            "naver_id": "",
            "name": "단어장",
            "href": "",
            "source_url": page.url,
            "raw_text": "",
        }]
    # De-dupe by stable-ish identity, then name.
    out, seen = [], set()
    for x in candidates:
        key = (x.get("naver_id") or "", x.get("href") or "", x["name"])
        if key not in seen:
            seen.add(key)
            out.append(x)
    return out

def extract_cards(page, wordbook: dict) -> list[dict]:
    selectors = [
        "[class*='wordbook'] li", "[class*='Wordbook'] li",
        "[class*='wordbook'] [role='listitem']", "[class*='Wordbook'] [role='listitem']",
        "[class*='card']", "[class*='Card']", "li",
    ]
    cards, seen = [], set()
    for selector in selectors:
        try:
            loc = page.locator(selector)
            for i in range(min(loc.count(), 5000)):
                el = loc.nth(i)
                if not el.is_visible():
                    continue
                raw = visible_text(el)
                ls = lines(raw)
                if not ls or len(raw) > 3000 or len(ls[0]) > 200:
                    continue
                if ls[0].lower() in {"단어장", "로그인", "검색", "메뉴", "닫기"}:
                    continue
                key = raw[:2000]
                if key in seen:
                    continue
                seen.add(key)
                cards.append({
                    "word": ls[0],
                    "meaning": ls[1] if len(ls) > 1 else "",
                    "pronunciation": "",
                    "part_of_speech": "",
                    "example": "\n".join(ls[2:]),
                    "wordbook_id": wordbook.get("naver_id", ""),
                    "wordbook": wordbook.get("name", ""),
                    "source_url": page.url,
                    "raw_text": raw,
                })
        except Exception:
            continue
    return cards

def scroll_settle(page):
    for _ in range(12):
        page.mouse.wheel(0, 1800)
        page.wait_for_timeout(700)

def collect(page) -> tuple[list[dict], list[dict], list[dict]]:
    network = capture_network(page)
    page.goto(DEFAULT_URL, wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_timeout(4_000)
    scroll_settle(page)

    wordbooks = discover_wordbooks(page)
    all_cards = []
    visited = set()

    # First collect current main page.
    main = wordbooks[:]
    for wb in main:
        href = wb.get("href")
        target = wb.get("source_url") or page.url
        if target in visited:
            continue
        visited.add(target)
        try:
            if target != page.url:
                page.goto(target, wait_until="domcontentloaded", timeout=45_000)
                page.wait_for_timeout(2_500)
            scroll_settle(page)
            all_cards.extend(extract_cards(page, wb))
        except Exception:
            continue

    # If discovery only found generic UI labels, the main page still contributes.
    if not all_cards:
        fallback = {"naver_id": "", "name": "단어장", "source_url": page.url}
        all_cards.extend(extract_cards(page, fallback))

    # Deduplicate exact same membership/card.
    dedup = {}
    for c in all_cards:
        key = (c.get("word",""), c.get("meaning",""), c.get("wordbook_id",""), c.get("wordbook",""))
        dedup[key] = c
    return list(dedup.values()), wordbooks, network

def save_snapshot(mode, page, cards, wordbooks, network) -> Path:
    payload = {
        "captured_at": now_iso(), "mode": mode, "url": page.url, "title": page.title(),
        "wordbooks": wordbooks, "cards": cards, "network": network,
    }
    path = EXPORT_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{mode}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path

def upsert_db(cards, wordbooks):
    init_db()
    now = now_iso()
    with sqlite3.connect(DB_PATH) as db:
        db.execute("PRAGMA foreign_keys=ON")
        wb_map = {}
        for wb in wordbooks:
            name = wb.get("name") or "단어장"
            nid = wb.get("naver_id") or None
            db.execute("""
                INSERT INTO wordbooks(naver_id,name,source_url,first_seen,last_seen,raw_json)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(naver_id,name) DO UPDATE SET
                  source_url=excluded.source_url,last_seen=excluded.last_seen,raw_json=excluded.raw_json
            """, (nid,name,wb.get("source_url",""),now,now,json.dumps(wb,ensure_ascii=False)))
            row = db.execute("SELECT id FROM wordbooks WHERE naver_id IS ? AND name=?", (nid,name)).fetchone()
            wb_map[(nid,name)] = row[0]

        for c in cards:
            word, meaning = c.get("word",""), c.get("meaning","")
            db.execute("""
                INSERT INTO words(word,meaning,pronunciation,part_of_speech,example,source_url,first_seen,last_seen,raw_json)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(word,meaning) DO UPDATE SET
                  pronunciation=excluded.pronunciation,part_of_speech=excluded.part_of_speech,
                  example=excluded.example,source_url=excluded.source_url,last_seen=excluded.last_seen,
                  raw_json=excluded.raw_json
            """, (word,meaning,c.get("pronunciation",""),c.get("part_of_speech",""),
                  c.get("example",""),c.get("source_url",""),now,now,json.dumps(c,ensure_ascii=False)))
            wid = db.execute("SELECT id FROM words WHERE word=? AND meaning=?", (word,meaning)).fetchone()[0]
            nid = c.get("wordbook_id") or None
            name = c.get("wordbook") or "단어장"
            wbid = wb_map.get((nid,name))
            if wbid:
                db.execute("""
                    INSERT INTO wordbook_words(wordbook_id,word_id,first_seen,last_seen,raw_json)
                    VALUES(?,?,?,?,?)
                    ON CONFLICT(wordbook_id,word_id) DO UPDATE SET
                      last_seen=excluded.last_seen,raw_json=excluded.raw_json
                """, (wbid,wid,now,now,json.dumps(c,ensure_ascii=False)))
        db.commit()

def write_repo_export(cards, wordbooks, snapshot_path):
    words = {}
    memberships = {}
    for c in cards:
        key = (c.get("word",""), c.get("meaning",""))
        words.setdefault(key, {
            "word": c.get("word",""), "meaning": c.get("meaning",""),
            "pronunciation": c.get("pronunciation",""),
            "part_of_speech": c.get("part_of_speech",""),
            "example": c.get("example",""), "source_url": c.get("source_url",""),
        })
        memberships.setdefault(key, [])
        label = c.get("wordbook") or "단어장"
        if label not in memberships[key]:
            memberships[key].append(label)
    for key, v in words.items():
        v["wordbooks"] = memberships[key]

    payload = {
        "schema_version": 2,
        "updated_at": now_iso(),
        "source": "naver_dictionary_personal_wordbooks",
        "wordbooks": wordbooks,
        "words": list(words.values()),
        "count": len(words),
        "membership_count": sum(len(v) for v in memberships.values()),
        "snapshot": str(snapshot_path),
    }
    REPO_EXPORT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def run(mode):
    ensure_dirs()
    init_db()
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=(mode != "bootstrap"),
            viewport={"width":1440,"height":1000},
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        try:
            if mode == "bootstrap":
                page.goto(DEFAULT_URL, wait_until="domcontentloaded", timeout=60_000)
                print("\nNAVER 로그인 → 모든 개인 단어장이 보이는 화면까지 이동 → ENTER.")
                input()
                cards, wordbooks, network = collect(page)
            else:
                cards, wordbooks, network = collect(page)
            path = save_snapshot(mode,page,cards,wordbooks,network)
            print(f"URL: {page.url}")
            print(f"Wordbooks discovered: {len(wordbooks)}")
            for wb in wordbooks:
                print(f"  - {wb.get('name')} | {wb.get('naver_id') or '-'} | {wb.get('source_url')}")
            print(f"Cards: {len(cards)}")
            print(f"Network captures: {len(network)}")
            print(f"Snapshot: {path}")
            if mode == "probe":
                return 0
            if not cards:
                print("ERROR: no cards detected. Keep the snapshot and tighten selectors/API parsing.")
                return 2
            upsert_db(cards,wordbooks)
            write_repo_export(cards,wordbooks,path)
            print(f"Export: {REPO_EXPORT}")
            print(f"SQLite: {DB_PATH}")
            return 0
        finally:
            browser.close()

def main():
    ap=argparse.ArgumentParser()
    g=ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--bootstrap",action="store_true")
    g.add_argument("--probe",action="store_true")
    g.add_argument("--sync",action="store_true")
    args=ap.parse_args()
    return run("bootstrap" if args.bootstrap else "probe" if args.probe else "sync")

if __name__=="__main__":
    raise SystemExit(main())
