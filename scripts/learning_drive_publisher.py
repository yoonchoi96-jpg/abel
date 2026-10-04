#!/usr/bin/env python3
"""Publish Abel learning snapshots to a Google Drive bridge.

Abel remains the source of truth. The bridge owns Google authentication.
This publisher can rebuild snapshots from the durable/local learning DB
before publishing; it never invents learning records.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

from learning_snapshot import build_snapshot, render_markdown
from learning_session import connect

SCHEMA_VERSION = "abel.learning.drive-payload.v2"


def _languages(db_path: str | Path) -> list[str]:
    con = connect(db_path)
    try:
        rows = con.execute(
            "SELECT DISTINCT language FROM learning_sessions WHERE language IS NOT NULL"
        ).fetchall()
        rows += con.execute(
            "SELECT DISTINCT language FROM writing_corrections WHERE language IS NOT NULL"
        ).fetchall()
    finally:
        con.close()
    return sorted({r[0] for r in rows if r[0]})


def rebuild_snapshots(db_path: str | Path, snapshot_dir: str | Path) -> list[str]:
    root = Path(snapshot_dir)
    root.mkdir(parents=True, exist_ok=True)
    languages = _languages(db_path)
    for language in languages:
        snap = build_snapshot(language, db_path)
        stem = language.replace("/", "_")
        (root / f"{stem}.json").write_text(
            json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (root / f"{stem}.md").write_text(render_markdown(snap), encoding="utf-8")
    (root / "index.json").write_text(
        json.dumps({
            "schema_version": "abel.learning.index.v2",
            "source": "Abel local learning DB",
            "languages": languages,
            "files": [f"{x}.json" for x in languages],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return languages


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
        bridge_url, data=body,
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
    parser.add_argument("--db", default="data/abel_learning.db")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--out", default="")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--bridge-url", default=os.environ.get("ABEL_DRIVE_BRIDGE_URL", ""))
    args = parser.parse_args()

    if args.rebuild:
        languages = rebuild_snapshots(args.db, args.snapshots)
    else:
        languages = None

    payload = build_payload(args.snapshots)
    if args.out:
        Path(args.out).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    if args.publish:
        if not args.bridge_url:
            raise SystemExit("ABEL_DRIVE_BRIDGE_URL is required for --publish")
        print(json.dumps(publish(payload, args.bridge_url), ensure_ascii=False))
    else:
        print(json.dumps({
            "status": "ready",
            "schema_version": SCHEMA_VERSION,
            "languages": languages if languages is not None else sorted(payload["snapshots"]),
            "snapshot_count": len(payload["snapshots"]),
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
