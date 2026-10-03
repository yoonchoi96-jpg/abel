# Abel HSK Evaluation Engine v1.1

Abel's HSK QA is deliberately split into two layers.

## Layer 1 — deterministic QA

`scripts/hsk_evaluation_engine.py` checks properties that do not require an LLM:

- answer distribution
- repeated answer runs
- question count and part ranges
- malformed questions/options
- duplicate stems/options
- concentration of absolute/extreme wording in distractors
- correct-option-as-uniquely-longest bias
- option length outliers
- surface/grammar-shape leakage

These are warnings unless the structure is invalid; they are not claims that an individual question is semantically wrong.

## Layer 2 — semantic/expert QA

The same module builds a Gemini-ready adversarial review prompt covering recurring expert-review findings:

- answer uniqueness / multiple valid answers
- distractor plausibility
- copied wording / shallow paraphrase
- transcript-question-answer consistency
- explanation consistency with the current revision
- natural contemporary Mandarin
- factual accuracy requiring verification
- repeated error-type design
- one-token/one-blank triviality
- regression after a revision

The deterministic report tells the reviewer what can be measured, while the LLM layer decides what requires linguistic or semantic judgment. The semantic reviewer must return exactly one question review for every supplied question number; unresolved factual verification also prevents release.

## MCP

`evaluate_hsk_content` is exposed by `scripts/abel_mcp_server.py`.

Inputs:
- `questions_json`: JSON array of question objects
- `transcript`: optional source transcript
- `reference_facts`: optional fact/reference notes
- `expected_total`: optional expected question count
- `expected_distribution_json`: optional expected answer distribution, e.g. `{"A":22,"B":23,"C":23,"D":22}`

The tool returns the deterministic report plus `semantic_review_prompt`.

## Intended generation loop

1. Gemini Spark generates the mock exam.
2. Abel deterministic QA runs.
3. Gemini performs semantic/expert QA using the returned review prompt.
4. Failures are revised.
5. Abel QA runs again.
6. The revised version is checked for regression before acceptance.

Abel must never treat a single reviewer comment as a permanent prohibition. New reviewer feedback should be generalized only when it represents a reusable evaluation rule.


## Release gate

The MCP surface exposes two QA stages:

1. `evaluate_hsk_content` runs deterministic structural/statistical checks and returns `semantic_review_prompt`.
2. Gemini (or another semantic reviewer) evaluates that prompt and returns the documented JSON review contract.
3. `finalize_hsk_review` combines the deterministic report with the semantic JSON.
4. A missing semantic review is **REVIEW**, never PASS. A semantic review with `pass=false` or any `critical_issues` is **REVIEW**. Only a deterministic PASS plus a valid semantic PASS with no critical issues produces `release_ready=true`.

This keeps the Python service from pretending it can judge Mandarin semantics while still giving the calling agent a hard machine-readable release gate.

## Live MCP smoke test

`scripts/mcp_smoke_test.py` now verifies that the live server exposes:

- `generate_lesson_audio`
- `evaluate_hsk_content`
- `finalize_hsk_review`

It also executes the two QA tools with a minimal fixture after MCP initialization.


## Gate contract hardening

The evaluate_hsk_content tool keeps the deterministic QA status (PASS, REVIEW, or FAIL) in status and uses tool_status="success" only for transport/tool success. This prevents a successful MCP invocation from masking a failed QA report.

The finalize_hsk_review tool now blocks release when:
- deterministic status is anything other than PASS
- semantic pass is not a real boolean
- the semantic review has malformed arrays or question-review entries
- question-review coverage does not exactly match the deterministic question numbers
- any question review is revise or reject
- unresolved factual verification items remain

The release gate is therefore a composition of deterministic QA plus complete semantic review, rather than a best-effort JSON merge.

## CI parity

The validation workflow installs both the general project dependencies and the production MCP dependency set from requirements-mcp.txt, then imports the production MCP server and checks that the three required tool functions register before running the full test suite.
