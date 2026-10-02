#!/usr/bin/env bash
set -euo pipefail

# Abel Remote MCP one-shot deployment.
# Run from the repository root on the Mac that has gcloud credentials.

REGION="${REGION:-asia-northeast3}"
SERVICE="${SERVICE:-abel-mcp}"

command -v gcloud >/dev/null || { echo "ERROR: gcloud CLI not found."; exit 1; }
gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q . || {
  echo "ERROR: no active gcloud account. Run: gcloud auth login"
  exit 1
}

PROJECT="${PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
[ -n "$PROJECT" ] && [ "$PROJECT" != "(unset)" ] || {
  echo "ERROR: no GCP project. Run: gcloud config set project YOUR_PROJECT"
  exit 1
}

APPS_SCRIPT_URL="${ABEL_APPS_SCRIPT_URL:-$(python3 - <<'PY'
import re
from pathlib import Path
p=Path("scripts/gemini_audio_executor.py")
if not p.exists():
    raise SystemExit("")
s=p.read_text()
m=re.search(r'default=.*?(https://script\.google\.com/macros/s/[^"\']+/exec)', s)
if not m:
    m=re.search(r'https://script\.google\.com/macros/s/[^"\']+/exec', s)
print(m.group(1) if m else "")
PY
)}"

[ -n "$APPS_SCRIPT_URL" ] || {
  echo "ERROR: could not determine ABEL_APPS_SCRIPT_URL."
  echo "Set it explicitly: export ABEL_APPS_SCRIPT_URL='https://script.google.com/.../exec'"
  exit 1
}

echo "== Abel MCP deploy =="
echo "project : $PROJECT"
echo "region  : $REGION"
echo "service : $SERVICE"
echo "apps script: $APPS_SCRIPT_URL"
echo

gcloud run deploy "$SERVICE"   --source .   --region "$REGION"   --project "$PROJECT"   --set-env-vars "ABEL_APPS_SCRIPT_URL=$APPS_SCRIPT_URL"   --quiet

URL="$(gcloud run services describe "$SERVICE"   --region "$REGION"   --project "$PROJECT"   --format='value(status.url)')"

echo
echo "MCP URL: $URL/mcp"
echo "Health:"
curl -fsS "$URL/" || true
echo
echo
echo "Next: python3 scripts/mcp_smoke_test.py "$URL/mcp""
