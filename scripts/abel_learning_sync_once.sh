#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
DB="${ABEL_LEARNING_DB:-data/abel_learning.db}"
SNAPSHOTS="${ABEL_SNAPSHOT_DIR:-data/learning_snapshots}"

"$PYTHON" scripts/learning_snapshot.py --all
"$PYTHON" scripts/abel_learning_drive_sync.py --snapshots "$SNAPSHOTS"
