# Abel → Google Drive automation

## 1. Persistent learning snapshots
GitHub Actions builds `data/learning_snapshots/*.json`. The optional publisher sends one language snapshot payload to a Google Apps Script bridge.

## 2. Drive bridge
The reference Apps Script endpoint should be deployed outside GitHub (Google Apps Script or an equivalent Drive bridge). Configure the bridge with:
- `ABEL_LEARNING_ROOT_FOLDER_ID` = the existing Abel Learning folder ID
- `ABEL_DRIVE_BRIDGE_TOKEN` = a long random token

Deploy the script as a Web App with access appropriate to the account that owns the Drive folder. Keep the token private.

## 3. GitHub Actions
Set GitHub repository secret `ABEL_DRIVE_BRIDGE_URL` to the deployed web-app URL. Optionally set `ABEL_DRIVE_BRIDGE_TOKEN` and append it to the URL only if the bridge is configured to require it.

The safer default is to put the token in a header, but Apps Script web apps do not expose arbitrary authorization headers consistently; for this reference implementation use a URL parameter only if needed and protect the deployment URL. A production bridge should add request signing/replay protection.

## 4. Question bank
Drive material indexing is intentionally separate. Once a Drive scan/export produces a manifest, run:
```bash
python scripts/question_bank_index.py drive_manifest.json --out data/question_bank_index.json
```
No file is invented when Drive access is unavailable.

## 5. Learning sessions
Use `scripts/learning_session.py` to record actual study events. This is local event storage; long-term persistence should be included in the next snapshot/Drive payload.

## 6. Adaptive planning
`scripts/adaptive_learning_plan.py` generates a transparent plan from actual snapshot evidence. It does not invent weaknesses.
