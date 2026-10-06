# Abel: GitHub Actions → Gemini TTS → Google Drive

## Production architecture

```
GitHub Actions
  ↓
Abel Gemini lesson generation
  ↓
Spoken-Mandarin QA / one repair pass
  ↓
Gemini 3.8 Flash TTS
  ↓
MP3
  ↓
Google Drive API
  ↓
Abel/AUDIO/YYYY-MM-DD/
```

Apps Script and Cloud Run are outside the new production audio path.

## One-time setup

Authentication uses the existing Workload Identity Federation setup (service account `abel-github-deploy@gen-lang-client-0543639616.iam.gserviceaccount.com`), the same as `deploy-abel-mcp.yml`. No JSON key is created or needed.

1. Drive API is enabled in the GCP project (done by `deploy-abel-mcp.yml`).
2. Share the `Abel` Drive folder with that service-account email as Editor/Writer.
3. Optionally set GitHub Actions secret `ABEL_DRIVE_FOLDER_ID` (otherwise the repo default folder ID is used).
4. Keep `GEMINI_API_KEY`.

If `GCP_SA_KEY` is set in the environment, `drive_audio_uploader.py` still uses it first; otherwise it uses Application Default Credentials.

Drive permissions on a parent folder propagate to child items, so one share on the Abel folder is sufficient for this publisher.

## Runtime

Gemini generates the lesson, Abel performs spoken-Mandarin QA, Gemini TTS renders the final script with `gemini-3.8-flash-tts` / `Kore`, and the runner uploads the MP3 directly through Drive API.

The runner also maintains `AUDIO/YYYY-MM-DD/`, `OUTBOX/`, and `LOG/`.

No Apps Script URL and no Cloud Run URL are used by this workflow.
