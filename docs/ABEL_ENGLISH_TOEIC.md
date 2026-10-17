# Abel English TOEIC Learning v1

This is an additive English module. Do not replace the Chinese / HSK
architecture. Reuse the existing learning_pipeline -> learning_session ->
review_state_engine -> learning_snapshot chain.

English uses language en-US, level TOEIC, and the Abel learning router
resolves English/Reading/TOEIC, English/Listening/TOEIC,
English/Speaking/TOEIC and English/Writing/TOEIC.

## Privacy and source

The user explicitly approved publishing the corrected 72-photo wordbook.
The source files now live in GitHub under data/toeic/:
- data/toeic/corrected_wordbook.txt (source table)
- data/toeic/wordbook_1086.json (1,086 analyzed vocabulary entries)
- data/toeic/ten_rounds.json (10-round practice allocation)
Only learner answers, generated instructor answer keys, and progress history
should remain under private/toeic/ (gitignored). The adapter preserves original
rank, Korean meaning, source photo/row, confidence, review status and the
yellow/blue/red/green learning marks. P1..P5 must match the distinct mark
count; rank is determined by number of colors first, latest colored review
second. These priorities indicate individual study history, NOT ETS
exam frequency.

Unresolved rows (검토/영어확인/뜻확인/위치확인 etc) can be studied but are
not eligible to become answer-key targets. User-corrected rows (수정완료)
are eligible. Never hallucinate a source word or missing colored mark.

## Commands from repository root

1) Import the GitHub-tracked corrected TXT, or use the ready-made JSON:

    python scripts/toeic_learning.py import data/toeic/corrected_wordbook.txt --out private/toeic/vocabulary.json

2) Use the committed ten_rounds.json or rebuild all ten study rounds:

    python scripts/toeic_learning.py plan private/toeic/vocabulary.json --out private/toeic/ten_rounds.json

3) Generate an Abel/Gemini provider request for original multiple-choice practice:

    python scripts/toeic_learning.py request private/toeic/vocabulary.json private/toeic/ten_rounds.json --round 1 --skill reading --out private/toeic/round01_request.json

4) Submit the external provider's authored instructor JSON for verification:

    python scripts/toeic_learning.py validate private/toeic/ten_rounds.json private/toeic/round01_paper.json --round 1 --out private/toeic/round01_valid.json

5) Hide instructor-only answers and generate student-facing paper:

    python scripts/toeic_learning.py student private/toeic/ten_rounds.json private/toeic/round01_paper.json --round 1 --out private/toeic/round01_student.json

6) Grade user answers and record in Abel learning / error / spacing system:

    python scripts/toeic_learning.py grade private/toeic/ten_rounds.json private/toeic/round01_paper.json private/toeic/round01_answers.json --round 1 --record --db private/toeic/abel_learning.db --out private/toeic/round01_result.json

User answers are a JSON object like {"q1":"B","q2":"C"}. The provider request
is only a generation CONTRACT: creating it does NOT generate questions.
No external API is called merely by creating these files.

## Curriculum

Ten rounds allocate every original word once into a core study pool,
roughly 108-109 words each, plus small rotating review terms from approved
P1-P3. Each *custom study exam* has exactly 50 questions:

    vocabulary 15; TOEIC-style Part 5 20; Part 6 5; Part 7 10.

The 50 questions cannot test all 109 words individually. Use untested
pool words in passages, explanations, flashcards, and Speaking/Writing.
Question validator enforces unique question IDs, unique target word IDs,
answer key A/B/C/D, distinct distractors, complete explanations and exact
section quotas. It does not independently prove linguistic correctness;
review machine-generated items before trusting them.

## TOEIC four skills

The request command also accepts --skill listening, --skill speaking and
--skill writing. Those requests provide constrained content generation
shapes (they are not yet actual tests).

Speaking: 11 questions, read aloud 1-2, picture 3-4, questions 5-7,
provided information 8-10, opinion 11. Without user audio, do not claim
to evaluate pronunciation.

Writing: 8 questions, picture-based sentences 1-5, email replies 6-7,
opinion essay 8. Use existing prepare_multilingual_writing_correction
for English corrections.

Listening: original scripts/questions need rendered, verified audio.
Do not reveal transcripts during a test. Without actual audio, disclose
that it is text/script practice.

ETS official TOEIC L&R has 100 Listening and 100 Reading questions
(200 total); the 50-item personalized practice exam is not official.
Do not claim to compute an official ETS 10-990 score from mock accuracy.

## Review and data persistence

The scored result uses language en-US, kind reading, and stable vocabulary
question IDs under a shared resource ID toeic-personal-wordbook, allowing
cross-round review histories. Existing Chinese zh-CN histories stay separate.
Snapshot/export durability in Cloud Run requires Abel's existing external
snapshot process rather than ephemeral container SQLite.

## Tests

    pytest -q tests/test_toeic_learning.py

The assistant has not configured unattended provider calls, uploaded
private vocabulary to the public repo, or deployed the MCP service.

## Published data quickstart

The three TOEIC source files are already versioned in GitHub.
After git pull, no external Drive import is necessary:

    mkdir -p private/toeic
    python scripts/toeic_learning.py request data/toeic/wordbook_1086.json data/toeic/ten_rounds.json --round 1 --skill reading --out private/toeic/round01_request.json

To regenerate the ten-round plan locally:

    python scripts/toeic_learning.py plan data/toeic/wordbook_1086.json --out private/toeic/ten_rounds_regenerated.json

The 68 entries needing manual review remain in the public wordbook for
study, but are NOT eligible as authoritative answer-key targets.
