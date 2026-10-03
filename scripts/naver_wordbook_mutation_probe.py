#!/usr/bin/env python3
"""
Abel - Naver Dictionary wordbook mutation probe.

This script is intentionally READ/OBSERVE-only from Abel's perspective:
the user performs ONE real mutation in the authenticated Naver UI
(add/remove/move a word), while Playwright captures the corresponding
XHR/fetch request and response metadata.

Purpose:
  1. Discover Naver's current authenticated mutation endpoint/payload.
  2. Avoid guessing undocumented write APIs.
  3. Provide the exact request shape needed for a future safe writer.

No mutation is initiated by this script.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timezone

DATA_ROOT = Path(os.environ.get("NAVER_WORDBOOK_DATA", "~/.naver_wordbook")).expanduser()
PROFILE_DIR = DATA_ROOT / "browser_profile"
OUT_DIR = DATA_ROOT / "mutation_probes"
DEFAULT_URL = "https://learn.dict.naver.com/wordbook/zhkodict/#/my/cards?wbId=9e2a3d82c347453d87a1013aa9f5ee8f&qt=0&st=0&name=%EB%82%B4%EA%B0%80%20%EC%B0%BE%EC%9D%80%20%EB%8B%A8%EC%96%B4&tab=list&page=1"

HOOK = r"""
(() => {
  if (window.__abelMutationProbe) return;
  window.__abelMutationProbe = [];

  const push = (kind, method, url, status, body, responseBody) => {
    try {
      window.__abelMutationProbe.push({
        kind,
        method: String(method || ""),
        url: String(url || ""),
        status: Number(status || 0),
        request_body: typeof body === "string" ? body.slice(0, 500000) : "",
        response_body: typeof responseBody === "string" ? responseBody.slice(0, 1000000) : ""
      });
    } catch (_) {}
  };

  const origFetch = window.fetch;
  window.fetch = async function(...args) {
    const req = args[0];
    const init = args[1] || {};
    const method = init.method || (req && req.method) || "GET";
    const requestBody = typeof init.body === "string"
      ? init.body
      : (req && typeof req.body === "string" ? req.body : "");
    const response = await origFetch.apply(this, args);
    try {
      const clone = response.clone();
      const responseBody = await clone.text();
      push("fetch", method, response.url || (req && req.url) || req,
           response.status, requestBody, responseBody);
    } catch (_) {}
    return response;
  };

  const origOpen = XMLHttpRequest.prototype.open;
  const origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(method, url, ...rest) {
    this.__abelMethod = method;
    this.__abelUrl = url;
    return origOpen.call(this, method, url, ...rest);
  };
  XMLHttpRequest.prototype.send = function(body) {
    this.__abelRequestBody = typeof body === "string" ? body : "";
    this.addEventListener("load", function() {
      let responseBody = "";
      try { responseBody = this.responseText || ""; } catch (_) {}
      push("xhr", this.__abelMethod, this.responseURL || this.__abelUrl,
           this.status, this.__abelRequestBody, responseBody);
    });
    return origSend.call(this, body);
  };
})();
"""

def main() -> int:
    from playwright.sync_api import sync_playwright

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            channel=os.environ.get("NAVER_BROWSER", "chrome"),
            headless=False,
            viewport={"width": 1440, "height": 1000},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.add_init_script(HOOK)

        page.goto(DEFAULT_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        print("\n=== Abel Naver mutation probe ===")
        print("1) 네이버 중국어 단어장이 로그인된 상태인지 확인")
        print("2) 실제로 단어 하나에 대해 원하는 작업을 딱 한 번 수행")
        print("   예: 단어 추가 / 삭제 / 다른 단어장으로 이동")
        print("3) 작업이 끝났으면 이 터미널에서 ENTER")
        input("\n작업 완료 후 ENTER: ")

        events = page.evaluate("window.__abelMutationProbe || []")
        interesting = []
        for event in events:
            url = str(event.get("url", "")).lower()
            method = str(event.get("method", "")).upper()
            if method not in {"GET", "HEAD"} or any(
                x in url for x in ("wordbook", "dict.naver", "learn.dict", "/api/", "/ajax/")
            ):
                interesting.append(event)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = OUT_DIR / f"{timestamp}_mutation.json"
        payload = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "url": page.url,
            "event_count": len(events),
            "interesting_count": len(interesting),
            "events": interesting,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"\nCaptured events: {len(events)}")
        print(f"Interesting mutation candidates: {len(interesting)}")
        print(f"Saved: {path}")
        print("\n다음 단계: 이 JSON에서 실제 mutation endpoint/method/payload를 확인한 뒤")
        print("Abel에 add/remove/move writer를 구현한다.")
        context.close()

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
