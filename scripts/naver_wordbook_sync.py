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
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

from playwright.sync_api import sync_playwright

DEFAULT_URL = "https://learn.dict.naver.com/wordbook/zhkodict/#/my/cards?wbId=9e2a3d82c347453d87a1013aa9f5ee8f&qt=0&st=0&name=%EB%82%B4%EA%B0%80%20%EC%B0%BE%EC%9D%80%20%EB%8B%A8%EC%96%B4&tab=list&page=1"
NAVER_DICT_BASE = "https://learn.dict.naver.com/wordbook/zhkodict/"
START_WB_ID = "9e2a3d82c347453d87a1013aa9f5ee8f"
START_WB_NAME = "내가 찾은 단어"

# Known personal wordbooks supplied from the user's authenticated Naver session.
# Unknown numbered HSK volumes are discovered separately from the wordbook UI.
SEED_WORDBOOKS = [
    {
        "naver_id": "9e2a3d82c347453d87a1013aa9f5ee8f",
        "name": "내가 찾은 단어",
        "source_url": DEFAULT_URL,
    },
    {
        "naver_id": "e96458b2504648af84f749e41aa00d6d",
        "name": "台湾旅行",
        "source_url": "https://learn.dict.naver.com/wordbook/zhkodict/#/my/cards?wbId=e96458b2504648af84f749e41aa00d6d&qt=0&st=0&name=%E5%8F%B0%E6%B9%BE%E6%97%85%E8%A1%8C&tab=list&page=1",
    },
    {
        "naver_id": "d2d50c21c29b4567bc1294d1360f61da",
        "name": "투투",
        "source_url": "https://learn.dict.naver.com/wordbook/zhkodict/#/my/cards?wbId=d2d50c21c29b4567bc1294d1360f61da&qt=0&st=0&name=%ED%88%AC%ED%88%AC&tab=list&page=1",
    },
    {
        "naver_id": "189253cd3de2425ba1dcb37a9fe124df",
        "name": "신HSK_6급 필수단어 10탄",
        "source_url": "https://learn.dict.naver.com/wordbook/zhkodict/#/my/cards?wbId=189253cd3de2425ba1dcb37a9fe124df&qt=0&st=0&name=%EC%8B%A0HSK_6%EA%B8%89%20%ED%95%84%EC%88%98%EB%8B%A8%EC%96%B4%2010%ED%83%84&tab=list&page=1",
    },
    {
        "naver_id": "c292bb7b12fd462a9b39310ebe3c29ab",
        "name": "신HSK_5급 필수단어 5탄",
        "source_url": "https://learn.dict.naver.com/wordbook/zhkodict/#/my/cards?wbId=c292bb7b12fd462a9b39310ebe3c29ab&qt=0&st=0&name=%EC%8B%A0HSK_5%EA%B8%89%20%ED%95%84%EC%88%98%EB%8B%A8%EC%96%B4%205%ED%83%84&tab=list&page=1",
    },
]
DATA_ROOT = Path(os.environ.get("NAVER_WORDBOOK_DATA", "~/.naver_wordbook")).expanduser()
PROFILE_DIR = DATA_ROOT / "browser_profile"
BROWSER_CHANNEL = os.environ.get("NAVER_BROWSER", "chrome").strip().lower()
EXPORT_DIR = DATA_ROOT / "exports"
DB_PATH = DATA_ROOT / "naver_wordbook.sqlite3"
REPO_EXPORT = Path(os.environ.get("NAVER_WORDBOOK_EXPORT", "data/naver_wordbook.json"))

NETWORK_HINTS = ("wordbook", "dict.naver", "learn.dict", "/api/", "/ajax/", "api.", "ajax.")
MAX_RESPONSE = 2_000_000

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def ensure_dirs() -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPO_EXPORT.parent.mkdir(parents=True, exist_ok=True)

def init_db() -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.execute("PRAGMA foreign_keys=ON")
        legacy = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='words'"
        ).fetchone()
        if legacy:
            cols = {r[1] for r in db.execute("PRAGMA table_info(words)").fetchall()}
            if "wordbook" in cols and "wordbook_words" not in {
                r[1] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }:
                db.execute("ALTER TABLE words RENAME TO words_legacy")
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
        legacy_exists = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='words_legacy'"
        ).fetchone()
        if legacy_exists:
            rows = db.execute(
                "SELECT word,meaning,pronunciation,part_of_speech,example,wordbook,source_url,first_seen,last_seen,raw_json FROM words_legacy"
            ).fetchall()
            for row in rows:
                word, meaning, pronunciation, pos, example, wb_name, source_url, first_seen, last_seen, raw_json = row
                db.execute("""
                    INSERT INTO words(word,meaning,pronunciation,part_of_speech,example,source_url,first_seen,last_seen,raw_json)
                    VALUES(?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(word,meaning) DO UPDATE SET
                      pronunciation=COALESCE(excluded.pronunciation,words.pronunciation),
                      part_of_speech=COALESCE(excluded.part_of_speech,words.part_of_speech),
                      example=COALESCE(excluded.example,words.example),
                      source_url=COALESCE(excluded.source_url,words.source_url),
                      first_seen=MIN(words.first_seen,excluded.first_seen),
                      last_seen=MAX(words.last_seen,excluded.last_seen),
                      raw_json=COALESCE(excluded.raw_json,words.raw_json)
                """, (word,meaning,pronunciation,pos,example,source_url,first_seen,last_seen,raw_json))
                if wb_name:
                    now = now_iso()
                    db.execute("""
                        INSERT INTO wordbooks(naver_id,name,source_url,first_seen,last_seen,raw_json)
                        VALUES(NULL,?,?,?,?,?)
                        ON CONFLICT(naver_id,name) DO UPDATE SET
                          source_url=COALESCE(excluded.source_url,wordbooks.source_url),
                          last_seen=MAX(wordbooks.last_seen,excluded.last_seen)
                    """, (wb_name,source_url,first_seen or now,last_seen or now,raw_json))
                    wbid = db.execute(
                        "SELECT id FROM wordbooks WHERE naver_id IS NULL AND name=?", (wb_name,)
                    ).fetchone()[0]
                    wid = db.execute(
                        "SELECT id FROM words WHERE word=? AND meaning=?", (word,meaning)
                    ).fetchone()[0]
                    db.execute("""
                        INSERT OR IGNORE INTO wordbook_words(wordbook_id,word_id,first_seen,last_seen,raw_json)
                        VALUES(?,?,?,?,?)
                    """, (wbid,wid,first_seen or now,last_seen or now,raw_json))
            db.execute("DROP TABLE words_legacy")
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
        resource_type = ""
        try:
            resource_type = response.request.resource_type or ""
        except Exception:
            pass
        if resource_type not in ("xhr", "fetch") and not any(h in url.lower() for h in NETWORK_HINTS):
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

def normalize_wordbook_name(name: str) -> str:
    """Collapse HSK numbered volumes into the user's requested collections."""
    name = (name or "").strip()
    if re.fullmatch(r"신HSK[_ ]?5급(?:[ _]필수단어)?[ _]\d+탄", name):
        return "신HSK 5급"
    if re.fullmatch(r"신HSK[_ ]?6급(?:[ _]필수단어)?[ _]\d+탄", name):
        return "신HSK 6급"
    return name

def expand_wordbook_manager(page) -> dict:
    """Open Naver's authenticated wordbook chooser/manager and return diagnostics."""
    diagnostics = {"clicked": [], "visible_text": "", "url": page.url}
    candidates = [
        page.get_by_text("중국어단어장", exact=True),
        page.locator("a,button,[role='button']").filter(has_text="중국어단어장"),
    ]
    for loc in candidates:
        try:
            for i in range(min(loc.count(), 5)):
                el = loc.nth(i)
                if not el.is_visible():
                    continue
                el.click(timeout=3000)
                page.wait_for_timeout(1200)
                diagnostics["clicked"].append("중국어단어장")
                break
            if diagnostics["clicked"]:
                break
        except Exception:
            continue
    try:
        diagnostics["visible_text"] = page.locator("body").inner_text(timeout=3000)[:50000]
    except Exception:
        pass
    diagnostics["url_after"] = page.url
    return diagnostics

def discover_wordbooks(page) -> list[dict]:
    found = {}

    def add(name="", href="", naver_id="", raw_text=""):
        name = (name or "").strip()
        href = (href or "").strip()
        naver_id = (naver_id or "").strip()
        if not name and not naver_id:
            return
        if not (naver_id or href or "단어장" in name or "HSK" in name.upper() or "여행" in name):
            return
        source_url = urljoin(page.url, href) if href else page.url
        key = naver_id or href or name
        found[key] = {
            "naver_id": naver_id,
            "name": name or f"wordbook:{naver_id}",
            "href": href,
            "source_url": source_url,
            "raw_text": raw_text or name,
        }

    # Current/legacy Naver wordbook URLs expose the stable wbId in the hash.
    try:
        anchors = page.locator("a[href*='wbId='], a[href*='#/my/cards']")
        for i in range(min(anchors.count(), 1000)):
            el = anchors.nth(i)
            if not el.is_visible():
                continue
            href = attr(el, "href")
            text = visible_text(el)
            m = re.search(r"[?&]wbId=([^&#]+)", href)
            add(text, href, m.group(1) if m else "", text)
    except Exception:
        pass

    # The private wordbook list is often loaded only after opening the
    # authenticated "중국어단어장" chooser. Do this before falling back to DOM
    # selectors so opaque wbIds are discovered rather than guessed.
    expand_wordbook_manager(page)
    for selector in ["a[href*='wbId=']", "a[href*='#/my/cards']", "[data-wb-id]", "[data-wordbook-id]", "[data-wordbookid]"]:
        try:
            loc = page.locator(selector)
            for i in range(min(loc.count(), 3000)):
                el = loc.nth(i)
                if not el.is_visible():
                    continue
                href = attr(el, "href")
                text = visible_text(el)
                data_id = attr(el, "data-wb-id") or attr(el, "data-wordbook-id") or attr(el, "data-wordbookid")
                m = re.search(r"[?&]wbId=([^&#]+)", href)
                add(text, href, data_id or (m.group(1) if m else ""), text)
        except Exception:
            pass

    # Older UI used #main_folder. Extract the folder label and clickable href/id
    # without depending on one exact CSS implementation.
    try:
        folder = page.locator("#main_folder")
        if folder.count():
            for el in folder.locator("a").all():
                if not el.is_visible():
                    continue
                href = attr(el, "href")
                text = visible_text(el)
                m = re.search(r"[?&]wbId=([^&#]+)", href)
                add(text, href, m.group(1) if m else "", text)
    except Exception:
        pass

    # Generic fallback for SPA versions where folder links are buttons.
    selectors = [
        "[data-wb-id]", "[data-wordbook-id]", "[data-wordbookid]",
        "[class*='wordbook']", "[class*='Wordbook']",
    ]
    for selector in selectors:
        try:
            loc = page.locator(selector)
            for i in range(min(loc.count(), 2000)):
                el = loc.nth(i)
                if not el.is_visible():
                    continue
                text = visible_text(el)
                href = attr(el, "href")
                data_id = (
                    attr(el, "data-wb-id") or attr(el, "data-wordbook-id")
                    or attr(el, "data-wordbookid")
                )
                if data_id or href or "단어장" in text or "HSK" in text.upper() or "여행" in text:
                    add(text, href, data_id, text)
        except Exception:
            continue

    m = re.search(r"[?&]wbId=([^&#]+)", page.url)
    if m:
        from urllib.parse import parse_qs, urlparse, unquote
        q = parse_qs(urlparse(page.url).query)
        current_name = unquote(q.get("name", [START_WB_NAME])[0]) or START_WB_NAME
        add(current_name, page.url, m.group(1), current_name)

    # Never fabricate a private wordbook from recommendation text.
    return list(found.values())

def extract_cards(page, wordbook: dict) -> list[dict]:
    selectors = [
        ".card_word",
        "li.card_word",
        ".inner_card",
        "[class*='card_word']",
        "[class*='inner_card']",
        "[class*='word_card']",
        "[class*='WordCard']",
        "[class*='card']",
        "li[class*='word']",
    ]
    cards, seen = [], set()
    for selector in selectors:
        try:
            loc = page.locator(selector)
            for i in range(min(loc.count(), 10000)):
                el = loc.nth(i)
                if not el.is_visible():
                    continue
                raw = visible_text(el)
                ls = lines(raw)
                if not ls or len(raw) > 10000:
                    continue

                word = ""
                try:
                    word = visible_text(el.locator(".title").first)
                except Exception:
                    pass
                if not word:
                    word = ls[0]
                word = re.sub(r"^[0-9]+[.)\\s]+", "", word).strip()
                if not word or len(word) > 300:
                    continue

                meanings = []
                try:
                    ml = el.locator(".list_mean")
                    for j in range(min(ml.count(), 50)):
                        t = visible_text(ml.nth(j))
                        if t:
                            meanings.append(t)
                except Exception:
                    pass
                meaning = "\n".join(meanings) if meanings else (ls[1] if len(ls) > 1 else "")
                key = (word, meaning, wordbook.get("naver_id",""))
                if key in seen:
                    continue
                seen.add(key)
                cards.append({
                    "word": word,
                    "meaning": meaning,
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

def page_info(page):
    try:
        current = visible_text(page.locator("#page_area div span").nth(0))
        spans = page.locator("#page_area div span")
        vals = [visible_text(spans.nth(i)) for i in range(min(spans.count(), 20))]
        nums = [x for x in vals if re.fullmatch(r"\\d+", x or "")]
        return (int(nums[0]), int(nums[1])) if len(nums) >= 2 else (1, 1)
    except Exception:
        return (1, 1)

def next_page(page) -> bool:
    try:
        area = page.locator("#page_area")
        buttons = area.locator("button")
        if buttons.count() < 2:
            return False
        btn = buttons.nth(1)
        disabled = attr(btn, "disabled")
        aria = attr(btn, "aria-disabled")
        cls = attr(btn, "class")
        if disabled or aria == "true" or "disabled" in cls:
            return False
        btn.click()
        page.wait_for_timeout(1200)
        return True
    except Exception:
        return False

def page_url(target: str, page_number: int) -> str:
    """Replace the hash-route page parameter without relying on UI pagination."""
    parsed = urlparse(target)
    fragment = parsed.fragment
    if not fragment:
        return target
    if "?" not in fragment:
        return target
    route, query = fragment.split("?", 1)
    params = parse_qs(query, keep_blank_values=True)
    params["page"] = [str(page_number)]
    new_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(fragment=f"{route}?{new_query}"))


def collect_wordbook(page, wb: dict) -> list[dict]:
    target = wb.get("source_url") or page.url
    try:
        if target != page.url:
            page.goto(target, wait_until="domcontentloaded", timeout=45_000)
        page.wait_for_timeout(1800)
        cards = []
        seen_signatures = set()
        target_page = 1

        # The Naver SPA exposes the page number in the hash route. Iterate the
        # route directly so collection does not depend on brittle pagination CSS.
        for _ in range(500):
            target = page_url(wb.get("source_url") or page.url, target_page)
            page.goto(target, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(1200)
            scroll_settle(page)

            page_cards = extract_cards(page, wb)
            signature = (
                target_page,
                tuple((c.get("word", ""), c.get("meaning", "")) for c in page_cards[:5]),
                len(page_cards),
            )
            if signature in seen_signatures:
                break
            seen_signatures.add(signature)

            if not page_cards:
                break

            cards.extend(page_cards)

            # A short/partial page is the natural terminal condition.
            if len(page_cards) < 20:
                break
            target_page += 1

        return cards
    except Exception:
        return []


def scroll_settle(page):
    for _ in range(12):
        page.mouse.wheel(0, 1800)
        page.wait_for_timeout(700)

def collect(page) -> tuple[list[dict], list[dict], list[dict]]:
    network = capture_network(page)
    page.goto(DEFAULT_URL, wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_timeout(3500)
    scroll_settle(page)

    wordbooks = discover_wordbooks(page)
    all_cards = []
    visited = set()

    # Main page may contain folders; visit every discovered stable wbId URL.
    for wb in wordbooks:
        target = wb.get("source_url") or page.url
        identity = wb.get("naver_id") or target
        if identity in visited:
            continue
        visited.add(identity)
        all_cards.extend(collect_wordbook(page, wb))


    dedup = {}
    for c in all_cards:
        key = (c.get("word",""), c.get("meaning",""), c.get("wordbook_id",""), c.get("wordbook",""))
        dedup[key] = c
    return list(dedup.values()), wordbooks, network

def save_snapshot(mode, page, cards, wordbooks, network) -> Path:
    payload = {
        "captured_at": now_iso(), "mode": mode, "url": page.url, "title": page.title(),
        "wordbooks": wordbooks, "cards": cards, "network": network,
        "final_dom_html": page.content()[:5_000_000],
        "final_local_storage": page.evaluate("Object.fromEntries(Object.entries(localStorage))"),
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
            raw_name = wb.get("name") or "단어장"
            name = normalize_wordbook_name(raw_name)
            nid = wb.get("naver_id") or None

            # HSK 5/6 numbered Naver volumes are intentionally collapsed into
            # one DB collection each. Keep the opaque Naver IDs only in raw_json.
            grouped = name in {"신HSK 5급", "신HSK 6급"}
            db_nid = None if grouped else nid
            db.execute("""
                INSERT INTO wordbooks(naver_id,name,source_url,first_seen,last_seen,raw_json)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(naver_id,name) DO UPDATE SET
                  source_url=excluded.source_url,last_seen=excluded.last_seen,raw_json=excluded.raw_json
            """, (db_nid,name,wb.get("source_url",""),now,now,json.dumps(wb,ensure_ascii=False)))
            row = db.execute("SELECT id FROM wordbooks WHERE naver_id IS ? AND name=?", (db_nid,name)).fetchone()
            if row:
                wb_map[(nid,raw_name)] = row[0]
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
            raw_name = c.get("wordbook") or "단어장"
            name = normalize_wordbook_name(raw_name)
            wbid = wb_map.get((nid,raw_name)) or wb_map.get((nid,name))
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

    grouped_wordbooks = {}
    for wb in wordbooks:
        name = normalize_wordbook_name(wb.get("name") or "단어장")
        entry = grouped_wordbooks.setdefault(name, {
            "name": name,
            "naver_ids": [],
            "source_urls": [],
        })
        if wb.get("naver_id") and wb["naver_id"] not in entry["naver_ids"]:
            entry["naver_ids"].append(wb["naver_id"])
        if wb.get("source_url") and wb["source_url"] not in entry["source_urls"]:
            entry["source_urls"].append(wb["source_url"])

    payload = {
        "schema_version": 3,
        "updated_at": now_iso(),
        "source": "naver_dictionary_personal_wordbooks",
        "wordbooks": list(grouped_wordbooks.values()),
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
        launch_kwargs = {
            "headless": (mode != "bootstrap"),
            "viewport": {"width": 1440, "height": 1000},
        }
        if BROWSER_CHANNEL in {"chrome", "msedge", "chrome-beta", "chrome-dev"}:
            launch_kwargs["channel"] = BROWSER_CHANNEL
        browser = p.chromium.launch_persistent_context(str(PROFILE_DIR), **launch_kwargs)
        page = browser.pages[0] if browser.pages else browser.new_page()
        try:
            if mode == "bootstrap":
                page.goto(DEFAULT_URL, wait_until="domcontentloaded", timeout=60_000)
                print("\nNAVER 로그인 → 실제 중국어 개인 단어장이 보이는 화면까지 이동 → ENTER.")
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
