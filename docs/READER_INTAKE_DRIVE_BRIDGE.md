# Reader intake with existing Drive OAuth

The additional `reader-intake-bridge.yml` workflow reuses Abel's existing user
Drive OAuth secrets **in place**. No secret values are read back or transferred
between repositories. It checks out the explicitly pinned, validated Reader ZIP
intake implementation from the public Abraham repository.

Only the private Drive **source request Doc ID** and an optional private output
folder ID are nonsecret dispatch inputs. The private source Doc contains a
`reader-source-request-v1` JSON request and an expiring Reader ZIP download URL.
Never put that URL or any credential into workflow inputs, public logs, or code.

Execution is restricted to GitHub's standard hosted Linux runner in this existing
public repository and manual dispatch on main. Google Drive must report sufficient
existing storage; no upgrade is attempted. Source ZIP bytes are preserved,
documents are processed sequentially with exact body/ID/URL deduplication,
errors are quarantined, and immutable verified data is committed to Drive using
a final manifest. The prior commit is authoritative until every upload succeeds.

This does not execute Abel TTS, Gemini, GCP deployment, Abraham's paid core,
DeepSeek, NAV production admission, or local Obsidian sync. It does not edit those
workflows or any deployed service. Intake JSONL is staged pending separate
Abraham/NAV QA. No automatic schedule is installed.

See the pinned implementation's `docs/reader-intake-zero-cost.md` for the
full preservation, validation and admission boundary.
