# Abel → Google Drive handoff

Abel is the source of truth for structured learning history. Google Drive is
the durable storage layer consumed by Gemini Education.

## Current boundary

Abel generates language-specific snapshots under `data/learning_snapshots/`.
The optional `scripts/learning_drive_publisher.py` packages those snapshots
into `abel.learning.drive-payload.v1`.

Google authentication is deliberately not embedded in Abel. A Google Apps
Script or equivalent Drive bridge can receive the payload through
`ABEL_DRIVE_BRIDGE_URL` and write the files into the user's Drive.

This keeps Google credentials out of GitHub and lets Gemini retain ownership
of the Drive-side organization.

## Local validation

```bash
python scripts/learning_drive_publisher.py --out /tmp/abel-drive-payload.json
```

## Publishing when a bridge exists

```bash
export ABEL_DRIVE_BRIDGE_URL="https://script.google.com/macros/s/.../exec"
python scripts/learning_drive_publisher.py --publish
```

No bridge URL means no network request is attempted.
