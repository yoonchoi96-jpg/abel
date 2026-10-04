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

1. Enable Google Drive API in the GCP project used by `GCP_SA_KEY`.
2. Share the existing `Abel` Drive folder with the service-account email from `GCP_SA_KEY` and grant Editor/Writer access.
3. Copy the existing `Abel` folder ID.
4. Add GitHub Actions secret `ABEL_DRIVE_FOLDER_ID`.
5. Keep `GEMINI_API_KEY` and `GCP_SA_KEY`.

Drive permissions on a parent folder propagate to child items, so one share on the Abel folder is sufficient for this publisher.

## Runtime

Gemini generates the lesson, Abel performs spoken-Mandarin QA, Gemini TTS renders the final script with `gemini-3.8-flash-tts` / `Kore`, and the runner uploads the MP3 directly through Drive API.

The runner also maintains `AUDIO/YYYY-MM-DD/`, `OUTBOX/`, and `LOG/`.

No Apps Script URL and no Cloud Run URL are used by this workflow.
