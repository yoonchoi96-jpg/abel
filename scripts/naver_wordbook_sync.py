#!/usr/bin/env python3
"""
Abel - Naver Dictionary personal wordbook synchronizer.

The authenticated browser profile stays on the user's Mac. This program never
reads or stores the Naver password. Use --bootstrap once, then --probe to
inspect the current Naver SPA and --sync for normal exports.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import time
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
CARD_SELECTORS = [
    "[class*='wordbook'] li",
    "[class*='Wordbook'] li",
    "[class*='wordbook'] [role='listitem']",
    "[class*='Wordbook'] [role='listitem']",
    "[class*='card']",
    "[class*='Card']",
    "li",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs() -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPO_EXPORT.parent.mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY,
                word TEXT NOT NULL,
                meaning TEXT,
                pronunciation TEXT,
                part_of_speech TEXT,
                example TEXT,
                wordbook TEXT,
                source_url TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                raw_json TEXT,
                UNIQUE(word, meaning, wordbook)
            )
            """
        )
        db.commit()


def normalize_lines(text: str) -> list[str]:
    return [x.strip() for x in re.split(r"\n+", text or "") if x.strip()]


def extract_dom_cards(page) -> list[dict]:
    seen: set[str] = set()
    cards: list[dict] = []

    for selector in CARD_SELECTORS:
        try:
            loc = page.locator(selector)
            count = min(loc.count(), 5000)
        except Exception:
            continue

        for i in range(count):
            try:
                el = loc.nth(i)
                if not el.is_visible():
                    continue
                raw = (el.inner_text(timeout=500) or "").strip()
            except Exception:
                continue

            lines = normalize_lines(raw)
            if not lines:
                continue

            # Reject generic navigation/footer list items.
            if len(raw) > 3000:
                continue
            word = lines[0]
            if len(word) > 200:
                continue

            key = raw[:2000]
            if key in seen:
                continue
            seen.add(key)

            cards.append(
                {
                    "word": word,
                    "meaning": lines[1] if len(lines) > 1 else "",
                    "pronunciation": "",
                    "part_of_speech": "",
                    "example": "\n".join(lines[2:]),
                    "wordbook": "",
                    "source_url": page.url,
                    "raw_text": raw,
                }
            )

    return cards


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
            if len(body) > 2_000_000:
                body = body[:2_000_000]
            text_body = body.decode("utf-8", errors="replace")
            events.append(
                {
                    "url": url,
                    "status": response.status,
                    "content_type": ctype,
                    "body": text_body,
                }
            )
        except Exception as exc:
            events.append({"url": url, "error": repr(exc)})

    page.on("response", on_response)
    return events


def wait_for_wordbook(page) -> None:
    page.goto(DEFAULT_URL, wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_timeout(4_000)

    # Give SPA navigation and lazy rendering time to settle.
    for _ in range(3):
        page.mouse.wheel(0, 1800)
        page.wait_for_timeout(1_500)


def save_snapshot(mode: str, page, cards: list[dict], network: list[dict]) -> Path:
    snapshot = {
        "captured_at": now_iso(),
        "mode": mode,
        "url": page.url,
        "title": page.title(),
        "cards": cards,
        "network": network,
    }
    path = EXPORT_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{mode}.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def upsert_db(cards: list[dict]) -> None:
    init_db()
    now = now_iso()
    with sqlite3.connect(DB_PATH) as db:
        for card in cards:
            db.execute(
                """
                INSERT INTO words
                    (word, meaning, pronunciation, part_of_speech, example,
                     wordbook, source_url, first_seen, last_seen, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(word, meaning, wordbook) DO UPDATE SET
                    pronunciation=excluded.pronunciation,
                    part_of_speech=excluded.part_of_speech,
                    example=excluded.example,
                    source_url=excluded.source_url,
                    last_seen=excluded.last_seen,
                    raw_json=excluded.raw_json
                """,
                (
                    card.get("word", ""),
                    card.get("meaning", ""),
                    card.get("pronunciation", ""),
                    card.get("part_of_speech", ""),
                    card.get("example", ""),
                    card.get("wordbook", ""),
                    card.get("source_url", ""),
                    now,
                    now,
                    json.dumps(card, ensure_ascii=False),
                ),
            )
        db.commit()


def write_repo_export(cards: list[dict], snapshot_path: Path) -> None:
    payload = {
        "schema_version": 1,
        "updated_at": now_iso(),
        "source": "naver_dictionary_wordbook",
        "source_url": DEFAULT_URL,
        "count": len(cards),
        "cards": cards,
        "snapshot": str(snapshot_path),
    }
    REPO_EXPORT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run(mode: str) -> int:
    ensure_dirs()

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=(mode != "bootstrap"),
            viewport={"width": 1440, "height": 1000},
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        network = capture_network(page)

        if mode == "bootstrap":
            page.goto(DEFAULT_URL, wait_until="domcontentloaded", timeout=60_000)
            print("\nNAVER에 로그인하고 내 단어장이 실제로 보이는 상태까지 만든 뒤 ENTER.")
            input()
            page.wait_for_timeout(2_000)
            cards = extract_dom_cards(page)
            path = save_snapshot(mode, page, cards, network)
            print(f"Bootstrap snapshot: {path}")
            print(f"Detected cards: {len(cards)}")
            browser.close()
            return 0

        try:
            wait_for_wordbook(page)
            cards = extract_dom_cards(page)
            path = save_snapshot(mode, page, cards, network)

            print(f"URL: {page.url}")
            print(f"Title: {page.title()}")
            print(f"Detected cards: {len(cards)}")
            print(f"Snapshot: {path}")
            print(f"Network captures: {len(network)}")

            if mode == "probe":
                browser.close()
                return 0

            if not cards:
                print(
                    "ERROR: no wordbook cards detected. "
                    "Run --probe and inspect the latest snapshot before sync."
                )
                browser.close()
                return 2

            upsert_db(cards)
            write_repo_export(cards, path)
            print(f"Repository export: {REPO_EXPORT}")
            print(f"SQLite: {DB_PATH}")
        finally:
            browser.close()

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Open visible Chromium for one-time manual Naver login.",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Capture diagnostics without replacing the canonical export.",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Synchronize the wordbook into JSON and SQLite.",
    )
    args = parser.parse_args()

    selected = [args.bootstrap, args.probe, args.sync]
    if sum(selected) != 1:
        parser.error("choose exactly one of --bootstrap, --probe, --sync")

    return run("bootstrap" if args.bootstrap else "probe" if args.probe else "sync")


if __name__ == "__main__":
    raise SystemExit(main())
