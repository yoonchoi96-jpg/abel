#!/usr/bin/env bash
set -euo pipefail

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

[ -n "${ABEL_DRIVE_FOLDER_ID:-}" ] || {
  echo "ERROR: ABEL_DRIVE_FOLDER_ID is required."
  exit 1
}

[ -n "${GEMINI_API_KEY:-}" ] || {
  echo "ERROR: GEMINI_API_KEY is required for production Gemini TTS."
  exit 1
}

ENV_VARS="ABEL_DRIVE_FOLDER_ID=${ABEL_DRIVE_FOLDER_ID},GEMINI_API_KEY=${GEMINI_API_KEY},GEMINI_TTS_MODEL=${GEMINI_TTS_MODEL:-gemini-3.8-flash-tts},GEMINI_TTS_VOICE=${GEMINI_TTS_VOICE:-Kore}"
if [ -n "${MCP_AUTH_TOKEN:-}" ]; then
  ENV_VARS="$ENV_VARS,MCP_AUTH_TOKEN=$MCP_AUTH_TOKEN"
fi

echo "== Abel MCP deploy =="
echo "project : $PROJECT"
echo "region  : $REGION"
echo "service : $SERVICE"
echo "drive   : configured"
echo "gemini  : configured"
echo

gcloud run deploy "$SERVICE"   --source .   --region "$REGION"   --project "$PROJECT"   --set-env-vars "$ENV_VARS"   --quiet

URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT" --format='value(status.url)')"

echo
echo "MCP URL: $URL/mcp"
echo "Health:"
curl -fsS "$URL/" || true
echo
