#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
DB="${ABEL_LEARNING_DB:-data/abel_learning.db}"
SNAPSHOTS="${ABEL_SNAPSHOT_DIR:-data/learning_snapshots}"
QUEUES="${ABEL_DAILY_QUEUE_DIR:-data/learning_queues}"

"$PYTHON" scripts/learning_snapshot.py --all --db "$DB"
mkdir -p "$QUEUES"
while IFS= read -r LANGUAGE; do
  [ -z "$LANGUAGE" ] && continue
  SAFE_NAME="${LANGUAGE//\//_}"
  "$PYTHON" scripts/daily_learning_queue.py --language "$LANGUAGE" --db "$DB" --out "$QUEUES/${SAFE_NAME}.json"
done < <("$PYTHON" - "$DB" <<'PY'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
rows = con.execute("""
  SELECT DISTINCT language FROM practice_errors
  WHERE language IS NOT NULL AND language <> ''
  ORDER BY language
""")
for row in rows:
    print(row[0])
con.close()
PY
)
"$PYTHON" scripts/abel_learning_drive_sync.py --snapshots "$SNAPSHOTS"
