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


## Canonical subpart QA specification

### Listening
- Part 1: 8 — short spoken item + 4 choices; direct comprehension/paraphrase.
- Part 2: 20 — longer multi-turn/interview-style material + multiple 4-choice questions; speaker tracking, detail integration, purpose/attitude.
- Part 3: 12 — longer discourse + multiple 4-choice questions; main idea, structure, inference, attitude, purpose.
- Individual audio word counts and seconds are not treated as official fixed constants; practice timing must be labeled practice timing.

### Reading
- Part 1: 10 — 选词填空; vocabulary, grammar, collocation, semantic/register fit.
- Part 2: 10 — 选句填空; cohesion, reference, transitions, logic, paragraph structure.
- Part 3: 20 — 篇章阅读; main idea, detail, inference, attitude, purpose, structure, implication, paraphrase.
- Do not invent official fixed character counts for individual passages.

### Writing
- Task 1 / Q81: practical/applied writing, minimum 150 Chinese characters.
- Task 2 / Q82: topic/opinion writing, minimum 300 Chinese characters.
- QA checks task fulfillment, required information, audience/register, organization, coherence, accuracy, lexical precision, and naturalness.
- No invented official subscore weights or writing-only time limit.

### Speaking boundary
HSKK Advanced is a separate oral test and is not part of the 82-question written mock:
- Part 1: 听后复述, 3 questions, about 7 minutes.
- Part 2: 朗读, 1 question, about 2 minutes.
- Part 3: 回答问题, 2 questions, about 5 minutes.
- Total: 6 questions, about 24 minutes including 10 minutes preparation.
- Total score 100, pass 60; do not invent official subpart point weights.

The semantic QA prompt should verify that generated content matches these subpart purposes and does not import legacy HSK 2.0 structures.
