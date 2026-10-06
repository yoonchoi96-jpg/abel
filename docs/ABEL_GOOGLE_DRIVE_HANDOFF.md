# Abel → Google Drive handoff

Abel is the source of truth for structured learning history and lesson metadata. Google Drive is the durable storage layer consumed by Gemini Education.

## Current production boundary

For generated audio, Abel writes directly to the user's Google Drive with OAuth 2.0 user credentials.

```
Abel MCP / GitHub Actions
  ↓
Google OAuth 2.0 user credentials
  ↓
Google Drive Learning root
```

The Drive publisher routes lessons using canonical metadata:

```
Learning/
  ├── Chinese/
  │   ├── Reading/
  │   ├── Listening/
  │   ├── Writing/
  │   ├── Speaking/
  │   ├── Vocabulary/
  │   ├── Grammar/
  │   └── Culture/
  ├── Spanish/
  └── French/
```

Under the selected skill, content is further grouped by level and date.

## Authentication

GitHub stores the OAuth client ID, client secret, and refresh token as repository secrets. The refresh token is never committed to the repository and must not be pasted into chat, logs, or source files.

## Validation

`scripts/drive_audio_uploader.py --self-test` verifies that the configured OAuth credentials can access the configured Drive root.

The end-to-end TTS workflow is `.github/workflows/abel-gemini-drive-tts.yml`.
