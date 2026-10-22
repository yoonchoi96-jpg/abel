#!/usr/bin/env python3
"""Inspect Naver Chinese wordbook XHR/fetch *metadata* in the owner's local browser.

This is a diagnostic, not a Naver API client or a production synchronizer.
It never replays HTTP requests, copies cookies, or exports response content.
Only endpoint shapes and JSON field *types* are written to disk.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

MAIN_URL = "https://learn.dict.naver.com/wordbook/zhkodict/#/my/main"
PROFILE_DIR = Path.home() / ".naver_wordbook" / "browser_profile"
REPORT_PATH = Path.home() / "Documents" / "Abel_Naver_Wordbook" / "naver_api_probe.json"
MAX_RECORDS = 500
MAX_BODY_BYTES = 512_000
HINTS = ("wordbook", "word", "folder", "card", "voca", "wbid")
SENSITIVE_PATHS = ("login", "logout", "oauth", "token", "passport", "account", "signin", "auth")


def clean_field(value: object) -> str:
    """Never expose identifiers or arbitrary text as a JSON key."""
    name = str(value)
    return name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,39}", name) else "[redacted_field]"


def safe_path(path: str) -> str:
    parts = []
    for part in path.split("/"):
        if (len(part) > 30 or re.fullmatch(r"[0-9a-fA-F]{16,}", part)
                or re.fullmatch(r"\d{7,}", part) or "%" in part):
            parts.append("[id]")
        else:
            parts.append(re.sub(r"[^A-Za-z0-9_.~-]", "_", part))
    return "/".join(parts)


def sanitized_endpoint(url: str) -> dict | None:
    """No query values, fragments, or authentication materials are exported."""
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if host != "naver.com" and not host.endswith(".naver.com"):
        return None
    path = parsed.path.lower()
    if any(part in path for part in SENSITIVE_PATHS) or host.startswith("nid."):
        return None
    return {
        "host": host,
        "path": safe_path(parsed.path),
        "query_keys": sorted({clean_field(k) for k, _ in parse_qsl(parsed.query)}),
    }


def skeleton(value: object, depth: int = 0) -> dict:
    """Represent structure, not values: no words, meanings, names, IDs or tokens."""
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "bool"}
    if isinstance(value, (int, float)):
        return {"type": "number"}
    if isinstance(value, str):
        return {"type": "string"}
    if isinstance(value, list):
        out = {"type": "array", "length": len(value)}
        if value and depth < 5:
            out["item"] = skeleton(value[0], depth + 1)
        return out
    if isinstance(value, dict):
        out = {"type": "object", "field_count": len(value)}
        if depth < 5:
            out["fields"] = {
                clean_field(k): skeleton(v, depth + 1)
                for k, v in list(value.items())[:24]
            }
        return out
    return {"type": "other"}


def embedded_content_structure(value: object) -> dict:
    """Inspect saved-card content locally while never exporting the content."""
    if not isinstance(value, str):
        return {"format": "not_string"}
    import html
    from html.parser import HTMLParser

    sample = value[:20_000].strip()
    if not sample:
        return {"format": "empty"}
    try:
        parsed = json.loads(sample)
    except (ValueError, TypeError):
        pass
    else:
        if isinstance(parsed, (list, dict)):
            return {"format": "json_string", "schema": skeleton(parsed)}

    normalized = html.unescape(sample)
    if re.search(r"<[A-Za-z][A-Za-z0-9]*(?:\\s|>|/)", normalized):
        class Tags(HTMLParser):
            def __init__(self):
                super().__init__()
                self.tags: set[str] = set()
                self.attr_names: set[str] = set()

            def handle_starttag(self, tag, attrs):
                # Never store HTML text or attribute values.
                if re.fullmatch(r"[a-z][a-z0-9]{0,31}", tag):
                    self.tags.add(tag)
                for name, _ in attrs:
                    if name and re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", name):
                        self.attr_names.add(name)

        parser = Tags()
        parser.feed(normalized)
        return {
            "format": "html_fragment",
            "tags": sorted(parser.tags)[:40],
            "attribute_names": sorted(parser.attr_names)[:40],
        }

    return {
        "format": "plain_text",
        "contains_hanzi": bool(re.search(r"[\\u3400-\\u9fff]", sample)),
        "contains_hangul": bool(re.search(r"[\\uac00-\\ud7a3]", sample)),
        "contains_latin": bool(re.search(r"[A-Za-z]", sample)),
    }


def content_schema_for_word_cards(payload: object) -> dict | None:
    """Only process the first saved card and never export its values."""
    try:
        first = payload["data"]["m_items"][0]
        if isinstance(first, dict):
            return embedded_content_structure(first.get("content"))
    except (KeyError, IndexError, TypeError):
        pass
    return None


def relevance(endpoint: dict, shape: dict | None) -> int:
    hint = (endpoint["host"] + endpoint["path"]).lower()
    score = sum(2 for word in HINTS if word in hint)
    if shape:
        key_names = json.dumps(shape, ensure_ascii=False).lower()
        score += sum(1 for word in HINTS if word in key_names)
    return score


class MetadataCollector:
    def __init__(self) -> None:
        self.events: dict[tuple, dict] = {}
        self.dropped = 0

    def record(self, *, url: str, method: str, status: int,
               content_type: str, body: bytes | None = None) -> None:
        endpoint = sanitized_endpoint(url)
        if endpoint is None:
            return
        mime = (content_type or "").split(";")[0].strip().lower()
        schema = None
        embedded_schema = None
        if body is not None and len(body) <= MAX_BODY_BYTES and "json" in mime:
            try:
                payload = json.loads(body.decode("utf-8"))
                schema = skeleton(payload)
                if endpoint["path"].endswith("/mywordbook/word/list/search"):
                    embedded_schema = content_schema_for_word_cards(payload)
            except (ValueError, UnicodeError):
                pass
        score = relevance(endpoint, schema)
        if score == 0:
            return
        method = method.upper()
        key = (method, endpoint["host"], endpoint["path"],
               tuple(endpoint["query_keys"]))
        if key not in self.events and len(self.events) >= MAX_RECORDS:
            self.dropped += 1
            return
        prior = self.events.get(key, {})
        self.events[key] = {
            "method": method,
            **endpoint,
            "status_codes": sorted(set(prior.get("status_codes", []) + [int(status)])),
            "content_type": mime,
            "shape": schema or prior.get("shape"),
            "card_content_structure": embedded_schema or prior.get("card_content_structure"),
            "relevance_score": max(score, prior.get("relevance_score", 0)),
            "observations": prior.get("observations", 0) + 1,
        }

    def report(self) -> dict:
        return {
            "format": "abel.naver_api_probe.metadata.v1",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "mode": "local_read_only_metadata_only",
            "warning": "Not a verified API. No authenticated request replay was performed.",
            "metadata_only": True,
            "credentials_exported": False,
            "response_values_exported": False,
            "dropped_endpoint_groups": self.dropped,
            "candidate_endpoints": sorted(
                self.events.values(),
                key=lambda e: (-e["relevance_score"], -e["observations"],
                               e["host"], e["path"]),
            ),
        }


def has_word_cards(collector: MetadataCollector) -> bool:
    return any(
        event["path"].endswith("/mywordbook/word/list/search")
        for event in collector.events.values()
    )


def try_open_wordbook(page, collector: MetadataCollector) -> bool:
    """Navigate one *visible* saved-wordbook link; no account mutation."""
    selectors = [
        "#main_folder a[data-id]",
        "a[href*='wbId=']",
        "a[href*='#/my/cards']",
        "[data-wb-id]",
        "[data-wordbook-id]",
    ]
    for selector in selectors:
        try:
            loc = page.locator(selector)
            for index in range(min(loc.count(), 30)):
                item = loc.nth(index)
                if not item.is_visible():
                    continue
                item.click(timeout=2500)
                page.wait_for_timeout(1500)
                if has_word_cards(collector):
                    return True
        except Exception:
            continue

    try:
        item = page.get_by_text("내가 찾은 단어", exact=True).first
        if item.is_visible():
            item.click(timeout=2500)
            page.wait_for_timeout(1500)
    except Exception:
        pass
    return has_word_cards(collector)


def run_probe(duration: int, output: Path) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit("Install locally: python3 -m pip install playwright") from exc

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    output = output.expanduser().resolve()
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR), headless=False,
            viewport={"width": 1280, "height": 900},
        )
        collector = MetadataCollector()

        def on_response(response) -> None:
            try:
                req = response.request
                if req.resource_type not in ("fetch", "xhr"):
                    return
                endpoint = sanitized_endpoint(response.url)
                if endpoint is None:
                    return
                mime = response.headers.get("content-type", "")
                # Never inspect HTML, cookies, headers or authentication responses.
                body = None
                if "json" in mime.lower():
                    size_header = response.headers.get("content-length", "0")
                    if not size_header.isdigit() or int(size_header) <= MAX_BODY_BYTES:
                        body = response.body()
                collector.record(
                    url=response.url, method=req.method, status=response.status,
                    content_type=mime, body=body,
                )
            except Exception:
                # Network collection must never break ordinary browser navigation.
                return

        context.on("response", on_response)
        page = context.pages[0] if context.pages else context.new_page()
        try:
            page.goto(MAIN_URL, wait_until="domcontentloaded", timeout=60_000)
            print("네이버 중국어 단어장이 열렸습니다.")
            print("로그인이 필요하면 열린 브라우저에서 직접 로그인하세요.")
            input("로그인 후, 단어장 첫 화면이 보이면 터미널에서 Enter: ")
            page.goto(MAIN_URL, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(1700)
            if not has_word_cards(collector):
                if try_open_wordbook(page, collector):
                    print("단어장 폴더를 자동으로 열었고 단어 목록 응답을 감지했습니다.")
                else:
                    print("단어 목록 자동 열기 실패: 지금 열린 Chromium 창에서 '내가 찾은 단어'나 다른 단어장 폴더를 클릭하세요.")
            print("추가·삭제 없이 단어장 폴더를 탐색할 수 있습니다. 관찰 시간: {}초".format(duration))
            page.wait_for_timeout(duration * 1000)
            if not has_word_cards(collector):
                print("경고: word/list/search가 감지되지 않았습니다. JSON은 부분 진단본입니다.")
        finally:
            # Nothing is sent over the network except the user's normal Naver UI requests.
            report = collector.report()
            output.parent.mkdir(parents=True, exist_ok=True)
            temp = output.with_suffix(output.suffix + ".tmp")
            temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
            temp.replace(output)
            context.close()

    print("Saved sanitized report: {}".format(output))
    print("Candidate endpoint groups: {}".format(len(report["candidate_endpoints"])))
    for e in report["candidate_endpoints"][:10]:
        print("  score={:2d} {:4s} {}{} ({})".format(
            e["relevance_score"], e["method"], e["host"], e["path"],
            ",".join(map(str, e["status_codes"])),
        ))
    print("No API endpoint was authenticated or replayed by this probe.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--duration", type=int, default=75,
                    help="seconds to browse different folders (default: 75)")
    ap.add_argument("--output", type=Path, default=REPORT_PATH)
    args = ap.parse_args()
    if not 5 <= args.duration <= 600:
        ap.error("--duration must be 5..600 seconds")
    run_probe(args.duration, args.output)


if __name__ == "__main__":
    main()
