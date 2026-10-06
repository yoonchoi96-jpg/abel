#!/usr/bin/env python3
"""Local-only Hanping My Vocabulary inspector.

This is an inspection tool, not the production collector. It opens a visible
Playwright browser with a persistent profile, lets the user sign in normally,
and records local diagnostics outside the repository. It never writes cookies,
storage state, passwords, OTPs, or browser profiles into Git.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

DEFAULT_URL = "https://hanpingchinese.com/my-vocab/"
DEFAULT_PROFILE = Path.home() / ".abel" / "hanping-browser"
DEFAULT_OUT = Path.home() / ".abel" / "hanping-inspect"

def redact_url(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}{p.path}"

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args()

    args.profile.mkdir(parents=True, exist_ok=True)
    args.out.mkdir(parents=True, exist_ok=True)
    urls = []

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(args.profile),
            headless=False,
            viewport={"width": 1440, "height": 1000},
        )
        page = context.pages[0] if context.pages else context.new_page()

        def on_request(request) -> None:
            if request.resource_type in {"xhr", "fetch", "document", "script"}:
                u = redact_url(request.url)
                if u not in urls:
                    urls.append(u)

        page.on("request", on_request)
        page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout * 1000)

        print("Sign in to Hanping if necessary and open My Vocabulary.")
        input("When the vocabulary page is fully visible, press ENTER... ")
        page.wait_for_timeout(1500)

        (args.out / "page.html").write_text(page.content(), encoding="utf-8")

        storage_keys = page.evaluate(
            """() => ({
                localStorage: Object.keys(localStorage),
                sessionStorage: Object.keys(sessionStorage)
            })"""
        )
        (args.out / "storage_keys.json").write_text(
            json.dumps(storage_keys, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        indexeddb = page.evaluate(
            """async () => {
                if (!window.indexedDB || !indexedDB.databases) return [];
                return (await indexedDB.databases()).map(db => ({
                    name: db.name ?? null, version: db.version ?? null
                }));
            }"""
        )
        (args.out / "indexeddb.json").write_text(
            json.dumps(indexeddb, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        signals = page.evaluate(
            """() => ({
                title: document.title,
                bodyTextLength: (document.body?.innerText ?? "").length,
                bodyTextPreview: (document.body?.innerText ?? "").slice(0, 2000),
                links: [...document.links].slice(0, 100).map(a => ({
                    text: (a.innerText || "").trim(), href: a.href
                })),
                scripts: [...document.scripts].map(s => ({
                    src: s.src || null, type: s.type || null,
                    bytes: (s.textContent || "").length
                }))
            })"""
        )
        (args.out / "signals.json").write_text(
            json.dumps(signals, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (args.out / "network_urls.json").write_text(
            json.dumps(sorted(urls), ensure_ascii=False, indent=2), encoding="utf-8"
        )

        print(json.dumps({
            "url": redact_url(page.url),
            "output": str(args.out),
            "indexeddb": indexeddb,
            "network_url_count": len(urls),
            "warning": "Inspection output may contain private vocabulary; do not commit it."
        }, ensure_ascii=False, indent=2))
        context.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
