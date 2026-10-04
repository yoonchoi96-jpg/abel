# Abel HSK 3.0 Level 6 Evaluation Engine

Abel production QA now targets **HSK 3.0 Level 6**, not legacy HSK 2.0.

## Canonical full written mock

- Listening: 1–40 (40 questions)
- Reading: 41–80 (40 questions)
  - Part 1: 41–50 — 选词填空
  - Part 2: 51–60 — 选句填空
  - Part 3: 61–80 — 篇章阅读
- Writing: 81–82
  - 81: practical/applied writing, minimum 150 Chinese characters
  - 82: topic/opinion writing, minimum 300 Chinese characters

The production MCP tool rejects the legacy 101-question HSK 2.0 layout.

## Two-layer QA

### Layer 1 — deterministic QA

`scripts/hsk30_evaluation_engine.py` checks:

- exact 1–82 layout;
- duplicate/missing question numbers;
- listening/reading/writing part ranges;
- four-option/A-D format for questions 1–80;
- writing task type and minimum character declaration;
- answer distribution;
- repeated answer runs;
- option-length leakage;
- obvious extreme-word clues.

These are structural/statistical signals. They do not decide Mandarin semantic correctness.

### Layer 2 — semantic/expert QA

Gemini receives the generated adversarial review prompt and checks:

- answer uniqueness / multiple valid answers;
- distractor plausibility;
- natural contemporary Mandarin;
- transcript/passage alignment;
- paraphrase depth;
- factual accuracy requiring verification;
- HSK 3.0 Level 6 difficulty;
- Reading Part 1/2/3 skill alignment;
- writing task fulfillment;
- explanation consistency;
- regressions after revision.

## Release loop

1. Gemini generates HSK 3.0 Level 6 material.
2. Abel deterministic QA runs.
3. Gemini performs semantic/adversarial QA.
4. Failures are revised.
5. Abel QA runs again.
6. Semantic QA is repeated after revisions.
7. `finalize_hsk_review` is the release gate.

A missing semantic review is never PASS.

## Important boundary

Do not invent an official numeric HSK 3.0 Level 6 writing rubric. Abel may produce a descriptive practice score, but it must not be presented as an official HSK score.

Do not state a writing-only time limit as official unless a current authoritative source explicitly confirms it.
