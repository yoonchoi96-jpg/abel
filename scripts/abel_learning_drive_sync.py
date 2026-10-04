#!/usr/bin/env python3
"""Sync Abel learning snapshots to a local Google Drive sync folder.

Uses Google Drive for Desktop as a filesystem handoff. No Google/Gemini API
calls are made. Abel remains the source of truth.
"""
from __future__ import annotations
import argparse, json, os, tempfile
from pathlib import Path

SCHEMA_VERSION = "abel.learning.drive-sync.v1"

def drive_root(explicit: str = "") -> Path:
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("ABEL_DRIVE_DIR")
    if env:
        return Path(env).expanduser()
    cloud = Path.home() / "Library/CloudStorage"
    for drive in sorted(cloud.glob("GoogleDrive-*")):
        for name in ("My Drive", "내 드라이브"):
            p = drive / name / "Abel Learning"
            if p.parent.is_dir():
                return p
    raise SystemExit("Set ABEL_DRIVE_DIR to the local Google Drive/Abel Learning folder")

def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass

def sync(snapshot_dir: str | Path, drive_dir: str | Path) -> dict:
    src, dst = Path(snapshot_dir), Path(drive_dir)
    if not src.exists():
        raise FileNotFoundError(src)
    copied = []
    for path in sorted(src.iterdir()):
        if path.is_file() and path.suffix in {".json", ".md"}:
            atomic_write(dst / path.name, path.read_text(encoding="utf-8"))
            copied.append(path.name)
    result = {
        "schema_version": SCHEMA_VERSION,
        "source": "Abel",
        "snapshot_count": len([x for x in copied if x.endswith(".json") and x != "index.json"]),
        "files": copied,
    }
    atomic_write(dst / "_ABEL_SYNC_STATUS.json", json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--snapshots", default="data/learning_snapshots")
    p.add_argument("--drive-dir", default="")
    args = p.parse_args()
    print(json.dumps(sync(args.snapshots, drive_root(args.drive_dir)), ensure_ascii=False))

if __name__ == "__main__":
    main()
