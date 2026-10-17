# Abel English TOEIC Learning v1

This is an additive English module. Do not replace the Chinese / HSK
architecture. Reuse the existing learning_pipeline -> learning_session ->
review_state_engine -> learning_snapshot chain.

English uses language en-US, level TOEIC, and the Abel learning router
resolves English/Reading/TOEIC, English/Listening/TOEIC,
English/Speaking/TOEIC and English/Writing/TOEIC.

## Privacy and source

The source is the USER-CORRECTED 72-photo TOEIC vocabulary TXT (approximately
1,086 entries). Do not place this personal data in the public GitHub repo.
Keep the corrected TXT, normalized JSON, tests, answer keys, and learner
results under private/toeic/ (gitignored). The adapter preserves original
rank, Korean meaning, source photo/row, confidence, review status and the
yellow/blue/red/green learning marks. P1..P5 must match the distinct mark
count; rank is determined by number of colors first, latest colored review
second. These priorities indicate individual study history, NOT ETS
exam frequency.

Unresolved rows (검토/영어확인/뜻확인/위치확인 etc) can be studied but are
not eligible to become answer-key targets. User-corrected rows (수정완료)
are eligible. Never hallucinate a source word or missing colored mark.

## Commands from repository root

1) Import private TXT:

    python scripts/toeic_learning.py import "private/toeic/TOEIC_전체72장_사용자교정반영_최종검토본.txt" --out private/toeic/vocabulary.json

2) Split all vocabulary into ten balanced study rounds:

    python scripts/toeic_learning.py plan private/toeic/vocabulary.json --out private/toeic/ten_rounds.json

3) Create Gemini/Abel provider request for original multiple-choice exam:

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
