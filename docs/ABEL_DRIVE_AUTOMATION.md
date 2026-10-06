# Abel → Google Drive automation

## Production path

Abel's production audio path is:

```
Gemini lesson generation
  ↓
Gemini TTS
  ↓
Abel DrivePublisher
  ↓
Google Drive OAuth user credentials
  ↓
Learning/<Language>/<Skill>/<Level>/<YYYY-MM-DD>/
```

The production uploader uses these GitHub Actions secrets:
- `GOOGLE_DRIVE_OAUTH_CLIENT_ID`
- `GOOGLE_DRIVE_OAUTH_CLIENT_SECRET`
- `GOOGLE_DRIVE_OAUTH_REFRESH_TOKEN`
- `ABEL_DRIVE_FOLDER_ID`

There is **no Apps Script bridge** in the production audio path.

## Learning snapshots

GitHub Actions can build `data/learning_snapshots/*.json`. These snapshots are source-backed learning state and are consumed by Abel's learning/session pipeline.

## Question bank

Drive material indexing is intentionally separate. Once a Drive scan/export produces a manifest, run:

```bash
python scripts/question_bank_index.py drive_manifest.json --out data/question_bank_index.json
```

No file is invented when Drive access is unavailable.

## Learning sessions

Use `scripts/learning_session.py` to record actual study events. Long-term persistence is represented through learning snapshots.

## Adaptive planning

`scripts/adaptive_learning_plan.py` generates a transparent plan from actual snapshot evidence. It does not invent weaknesses.
