#!/usr/bin/env python3
"""Automatically discover Hanping exports on a Mac and run the Abel pipeline.

Only files whose filename or immediate parent contains "hanping" are eligible.
No login, cookies, browser sessions, cloud decryption, or credentials are used.
"""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "hanping" / ".auto_sync_state.json"
DEFAULT_DIRS = [
    Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Hanping",
    Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Downloads",
    Path.home() / "Downloads",
    Path.home() / "Documents",
]

def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def load_state() -> dict:
    if not STATE.exists():
        return {}
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def is_hanping_path(path: Path) -> bool:
    return "hanping" in f"{path.name} {path.parent.name}".lower()

def candidate_files(directories: list[Path], max_depth: int = 3) -> list[Path]:
    """Find Hanping exports without recursively crawling an entire home tree.

    A small bounded depth handles exports nested under iCloud/Downloads/Hanping
    folders while avoiding an unbounded scan of Documents or Downloads.
    """
    out = []
    allowed = {".json", ".csv", ".tsv", ".txt"}
    for directory in directories:
        if not directory.is_dir():
            continue
        base_depth = len(directory.parts)
        for path in directory.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in allowed:
                continue
            if len(path.parts) - base_depth - 1 > max_depth:
                continue
            if is_hanping_path(path) or any(
                "hanping" in part.lower()
                for part in path.relative_to(directory).parts[:-1]
            ):
                out.append(path)
    return sorted(set(out), key=lambda p: p.stat().st_mtime)

def process(path: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "hanping_sync.py"), str(path)],
        cwd=ROOT, check=True, capture_output=True, text=True
    )
    routed = ROOT / "data" / "hanping" / "routed.json"
    return json.loads(routed.read_text(encoding="utf-8"))

def run_once(directories: list[Path]) -> int:
    state = load_state()
    processed = 0
    for path in candidate_files(directories):
        digest = file_hash(path)
        key = str(path.resolve())
        if state.get(key) == digest:
            continue
        result = process(path)
        state[key] = digest
        save_state(state)
        print(f"HANPING AUTO-SYNC: {path.name} -> {result['route_counts']}")
        processed += 1
    return processed

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("directories", nargs="*", type=Path, default=DEFAULT_DIRS)
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--interval", type=int, default=30)
    args = ap.parse_args()
    while True:
        run_once([p.expanduser().resolve() for p in args.directories])
        if not args.watch:
            return
        time.sleep(max(5, args.interval))

if __name__ == "__main__":
    main()
