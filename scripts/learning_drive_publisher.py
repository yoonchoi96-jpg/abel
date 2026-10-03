#!/usr/bin/env python3
"""Publish Abel learning snapshots to a Google Drive bridge.

Abel remains the source of truth. This module is intentionally optional:
- without a bridge URL it only validates/builds a Drive-ready payload;
- with ABEL_DRIVE_BRIDGE_URL it POSTs snapshots to the user's Google Apps
  Script/Drive bridge.
The bridge owns Google authentication and Drive permissions.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

SCHEMA_VERSION = "abel.learning.drive-payload.v1"


def build_payload(snapshot_dir: str | Path = "data/learning_snapshots") -> dict:
    root = Path(snapshot_dir)
    if not root.exists():
        raise FileNotFoundError(f"Snapshot directory not found: {root}")

    files = {}
    for path in sorted(root.glob("*.json")):
        if path.name == "index.json":
            continue
        files[path.stem] = json.loads(path.read_text(encoding="utf-8"))

    index_path = root / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}

    return {
        "schema_version": SCHEMA_VERSION,
        "source": "Abel",
        "index": index,
        "snapshots": files,
    }


def publish(payload: dict, bridge_url: str, timeout: int = 60) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        bridge_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"status": "ok", "raw_response": raw[:3000]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshots", default="data/learning_snapshots")
    parser.add_argument("--out", default="")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--bridge-url", default=os.environ.get("ABEL_DRIVE_BRIDGE_URL", ""))
    args = parser.parse_args()

    payload = build_payload(args.snapshots)

    if args.out:
        Path(args.out).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if args.publish:
        if not args.bridge_url:
            raise SystemExit(
                "ABEL_DRIVE_BRIDGE_URL is required for --publish. "
                "Use --out to generate a Drive-ready payload without publishing."
            )
        print(json.dumps(publish(payload, args.bridge_url), ensure_ascii=False))
    else:
        print(json.dumps({
            "status": "ready",
            "schema_version": SCHEMA_VERSION,
            "languages": sorted(payload["snapshots"]),
            "snapshot_count": len(payload["snapshots"]),
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
