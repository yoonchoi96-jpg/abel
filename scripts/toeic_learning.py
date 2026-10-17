#!/usr/bin/env python3
"""Import the user's corrected TOEIC TSV, plan ten review-balanced practice rounds.

The personal wordbook is *not* committed to public GitHub. Read it locally or
from an explicitly exported private Drive file. Never invent questions/answers.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "abel.toeic.vocabulary.v1"
PLAN_SCHEMA = "abel.toeic.study-plan.v1"
PAPER_SCHEMA = "abel.toeic.practice-paper.v1"
LANGUAGE = "en-US"
LEVEL = "TOEIC"
QUOTAS = {"vocabulary": 15, "part5": 20, "part6": 5, "part7": 10}
COLORS = ("yellow", "blue", "red", "green")
REVIEW_OK = ("", "수정완료")


def _bool(text):
    return str(text).strip() in ("✓", "✔", "Y", "yes", "True", "1")


def import_txt(path):
    """Parse the user-corrected 12-column Korean tab-separated review sheet."""
    text = Path(path).read_text(encoding="utf-8-sig")
    words, seen = [], set()
    for line in text.splitlines():
        cells = line.split("\t")
        if len(cells) < 12 or not cells[0].isdecimal():
            continue
        number = int(cells[0])
        if number in seen:
            raise ValueError(f"duplicate original rank: {number}")
        seen.add(number)
        priority, expression, meaning = [c.strip() for c in cells[1:4]]
        if priority not in ("P1", "P2", "P3", "P4", "P5") or not expression or not meaning:
            raise ValueError(f"invalid vocabulary row: {number}")
        marks = {k: _bool(v) for k, v in zip(COLORS, cells[5:9])}
        count = sum(marks.values())
        expected = 5 - count if count else 5
        if priority != f"P{expected}":
            raise ValueError(f"priority/mark mismatch: {number}")
        review = cells[10].strip()
        words.append({
            "id": f"toeic-vocab-{number:04d}",
            "original_rank": number,
            "language": LANGUAGE,
            "expression": expression,
            "meaning_ko": meaning,
            "priority": priority,
            "review_marks": marks,
            "mark_count": count,
            "latest_review": max((i for i, v in enumerate(marks.values(), 1) if v), default=0),
            "source_location": cells[9].strip(),
            "review_status": review,
            "confidence": cells[11].strip(),
            "suggestion": cells[12].strip() if len(cells) > 12 else "",
            "eligible_for_answer_key": review in REVIEW_OK and bool(meaning),
        })
    if not words:
        raise ValueError("no vocabulary rows found")
    return {"schema_version": SCHEMA, "language": LANGUAGE, "source_title": Path(path).name,
            "count": len(words), "words": words}


def _load(source):
    if str(source).lower().endswith(".txt"):
        return import_txt(source)
    data = json.loads(Path(source).read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA or not isinstance(data.get("words"), list):
        raise ValueError("invalid TOEIC vocabulary JSON")
    return data


def plan_rounds(corpus, rounds=10):
    """Distribute *each* vocabulary item once into a study pool.

    High priority terms are spread across rounds instead of clustered, and
    additional review focus terms may be repeated between rounds.
    """
    if rounds != 10:
        raise ValueError("this curriculum requires ten rounds")
    groups = {p: [] for p in ("P1", "P2", "P3", "P4", "P5")}
    for word in corpus["words"]:
        groups[word["priority"]].append(word)
    pools = [[] for _ in range(rounds)]
    cursor = 0
    for priority in groups:
        for w in sorted(groups[priority], key=lambda x: (-x["latest_review"], x["original_rank"])):
            pools[cursor % rounds].append(w)
            cursor += 1
    focus = [w["id"] for p in ("P1", "P2", "P3") for w in groups[p]
             if w["eligible_for_answer_key"]]
    result = []
    for idx, pool in enumerate(pools):
        eligible = [w for w in pool if w["eligible_for_answer_key"]]
        if len(eligible) < sum(QUOTAS.values()):
            raise ValueError(f"round {idx + 1}: fewer than 50 eligible terms")
        repeated = ([focus[(idx * 11 + j) % len(focus)] for j in range(min(12, len(focus)))])
                    if focus else [])
        result.append({
            "round": idx + 1, "id": f"toeic-personal-{idx + 1:02d}",
            "difficulty": ("basic" if idx < 2 else "intermediate" if idx < 4
                           else "upper-intermediate" if idx < 6
                           else "advanced" if idx < 8 else "final-review"),
            "study_vocab_ids": [w["id"] for w in pool],
            "eligible_vocab_ids": [w["id"] for w in eligible],
            "extra_review_ids": repeated,
            "question_quota": dict(QUOTAS),
            "question_count": sum(QUOTAS.values()),
            "study_count": len(pool),
            "pending_review_count": len(pool) - len(eligible),
        })
    return {
        "schema_version": PLAN_SCHEMA,
        "language": LANGUAGE,
        "exam_system": "TOEIC",
        "mode": "personal_50_question_practice_not_official_TOEIC",
        "vocabulary_count": len(corpus["words"]),
        "requires_private_wordbook": True,
        "rounds": result,
    }


def _round(plan, number):
    if plan.get("schema_version") != PLAN_SCHEMA:
        raise ValueError("invalid plan")
    for entry in plan["rounds"]:
        if entry["round"] == number:
            return entry
    raise ValueError("unknown round")


def generation_request(corpus, plan, round_number, skill="reading"):
    """Return a source-grounded LLM request. Does NOT claim questions were generated."""
    entry = _round(plan, round_number)
    ids = set(entry["eligible_vocab_ids"]) | set(entry["extra_review_ids"])
    refs = [{"id": w["id"], "english": w["expression"], "meaning_ko": w["meaning_ko"],
             "priority": w["priority"], "source_location": w["source_location"]}
            for w in corpus["words"] if w["id"] in ids and w["eligible_for_answer_key"]]
    if skill == "reading":
        required = {
            "schema_version": PAPER_SCHEMA, "round_id": entry["id"],
            "questions": [{
                "id": "unique question id", "section": "vocabulary|part5|part6|part7",
                "stem": "English question and passage/context",
                "options": {"A": "text", "B": "text", "C": "text", "D": "text"},
                "answer": "A|B|C|D", "vocab_id": "one of supplied IDs",
                "explanation_ko": "why right, why distractors wrong"
            }]
        }
        rules = [
            "Create exactly 50 ORIGINAL four-choice questions (15 vocabulary, 20 Part 5, 5 Part 6, 10 Part 7).",
            "Each question must have exactly one defensible correct option and distinct option texts.",
            "Every target vocab_id must be unique within this round and from allowed IDs.",
            "Use business situations; Part 6/7 need meaningful coherent context.",
            "Do not reproduce ETS copyrighted questions.",
            "Keep the answer/explanation only in instructor JSON; student view hides them.",
            "Exclude all uncertain/flagged vocabulary from target answer keys.",
            "Keep vocabulary usage natural; do not force rare terms into implausible contexts.",
        ]
    elif skill == "speaking":
        required = {"round_id": entry["id"], "skill": "speaking",
                    "tasks": [{"number": n, "task_type": (
                        "read_aloud" if n <= 2 else "describe_picture" if n <= 4
                        else "respond_to_questions" if n <= 7
                        else "provided_information" if n <= 10 else "opinion"),
                        "prompt": "English prompt", "source_vocab_ids": []} for n in range(1, 12)]}
        rules = ["Create 11 original TOEIC Speaking-style tasks, 1-2 read, 3-4 picture, "
                 "5-7 questions, 8-10 provided info, 11 opinion.",
                 "Do not claim to grade pronunciation without actual audio.",
                 "If pictures/audio cannot be supplied, label them as simulated prompts.",
                 "Provide model answers separately from candidate tasks."]
    elif skill == "writing":
        required = {"round_id": entry["id"], "skill": "writing",
                    "tasks": [{"number": n, "task_type": (
                        "picture_sentence" if n <= 5 else "email_reply" if n <= 7 else "opinion_essay"),
                        "prompt": "English prompt", "source_vocab_ids": []} for n in range(1, 9)]}
        rules = ["Create 8 original TOEIC Writing-style tasks, 1-5 picture sentences, "
                 "6-7 email replies, 8 opinion essay.",
                 "Picture prompts without actual images must be labeled simulated.",
                 "Do not assign official scores without rubric-based evaluation."]
    elif skill == "listening":
        required = {"round_id": entry["id"], "skill": "listening",
                    "audio_script": "dialogue or talk", "questions": [],
                    "answer_key": {}, "transcript_hidden_until_submission": True}
        rules = ["Write original Part 1-4-style listening tasks with script and answer key.",
                 "No generated audio exists until TTS renders and audio is validated.",
                 "Hide the script and answer key from student materials."]
    else:
        raise ValueError("skill must be reading, listening, speaking or writing")
    return {
        "schema_version": "abel.toeic.generation-request.v1", "language": LANGUAGE,
        "level": LEVEL, "exam_system": "TOEIC", "round": round_number,
        "skill": skill, "source_of_truth": "Abel", "task_type": "mock_test",
        "prompt": ("Create ORIGINAL validated TOEIC practice content as JSON only. "
                   "Use only the approved vocabulary ids as answer-key targets. "
                   "Follow all required rules and output fields. "
                   "The exam writer MUST NOT reveal the instructor answers to students.\n"
                   + json.dumps({"rules": rules, "expected_result_shape": required,
                                 "allowed_vocabulary": refs}, ensure_ascii=False)),
        "profile": "personal-practice" if skill == "reading" else "official-structure-inspired",
        "allowed_vocabulary": refs,
        "rules": rules, "expected_result_shape": required,
        "status": "awaiting_external_question_authoring",
    }


def validate_paper(paper, entry):
    if paper.get("schema_version") != PAPER_SCHEMA or paper.get("round_id") != entry["id"]:
        raise ValueError("paper schema/round mismatch")
    questions = paper.get("questions")
    if not isinstance(questions, list) or len(questions) != entry["question_count"]:
        raise ValueError("paper must contain exactly 50 questions")
    counts, qids, vocab, stems = Counter(), set(), set(), set()
    eligible = set(entry["eligible_vocab_ids"]) | set(entry["extra_review_ids"])
    for q in questions:
        section, qid, vocab_id = q.get("section"), q.get("id"), q.get("vocab_id")
        if section not in QUOTAS or not qid or qid in qids:
            raise ValueError("invalid/duplicate question id or section")
        if not vocab_id or vocab_id not in eligible or vocab_id in vocab:
            raise ValueError("target word not in approved pool or duplicated")
        opts = q.get("options")
        if not isinstance(opts, dict) or set(opts) != {"A", "B", "C", "D"}:
            raise ValueError("each question needs A-D options")
        if any(not str(v).strip() for v in opts.values()) or len(set(opts.values())) != 4:
            raise ValueError("empty/duplicate choices")
        if q.get("answer") not in opts or not str(q.get("explanation_ko", "")).strip():
            raise ValueError("missing answer/explanation")
        stem = str(q.get("stem", "")).strip()
        if not stem or stem.casefold() in stems:
            raise ValueError("empty/duplicate question stem")
        qids.add(qid); vocab.add(vocab_id); stems.add(stem.casefold()); counts[section] += 1
    if dict(counts) != QUOTAS:
        raise ValueError(f"incorrect section quota: {dict(counts)}")
    return True


def student_view(paper, entry):
    validate_paper(paper, entry)
    return {"round_id": entry["id"], "mode": "student", "questions": [
        {"id": q["id"], "section": q["section"], "stem": q["stem"], "options": q["options"]}
        for q in paper["questions"]]}


def grade(paper, entry, answers):
    validate_paper(paper, entry)
    if not isinstance(answers, dict):
        raise ValueError("answers must be a question-id to choice dictionary")
    rows = []
    for q in paper["questions"]:
        actual = str(answers.get(q["id"], "")).strip().upper()
        correct = actual == q["answer"]
        rows.append({
            "question_id": q["vocab_id"],  # Stable across rounds for Abel spaced repetition.
            "exam_question_id": q["id"],
            "correct": correct, "answer": actual or None,
            "expected": q["answer"] if not correct else None,
            "error_type": None if correct else ("meaning" if q["section"] == "vocabulary" else
                                               "grammar" if q["section"] == "part5" else "reading_context"),
            "target_priority": None, "section": q["section"],
        })
    total = len(rows)
    correct = sum(r["correct"] for r in rows)
    return {
        "schema_version": "abel.toeic.scored-practice.v1", "kind": "reading",
        "language": LANGUAGE, "level": LEVEL, "exam_system": "TOEIC",
        "round_id": entry["id"], "resource_id": "toeic-personal-wordbook",
        "total": total, "correct": correct, "score": round(correct / total * 100, 2),
        "results": rows, "completed_at": datetime.now(timezone.utc).isoformat(),
        "source": "user-corrected-72-photo-TOEIC-wordbook",
        "source_links": [],
    }


def _write(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description="Abel private TOEIC 10-round import/plan/test workflow")
    sub = p.add_subparsers(dest="action", required=True)
    a = sub.add_parser("import"); a.add_argument("source"); a.add_argument("--out", required=True)
    a = sub.add_parser("plan"); a.add_argument("source"); a.add_argument("--out", required=True)
    a = sub.add_parser("request")
    a.add_argument("source"); a.add_argument("plan"); a.add_argument("--round", type=int, required=True)
    a.add_argument("--skill", choices=("reading", "listening", "speaking", "writing"), default="reading")
    a.add_argument("--out", required=True)
    for action in ("validate", "student", "grade"):
        a = sub.add_parser(action)
        a.add_argument("plan"); a.add_argument("paper"); a.add_argument("--round", type=int, required=True)
        a.add_argument("--out", required=True)
        if action == "grade":
            a.add_argument("answers"); a.add_argument("--record", action="store_true")
            a.add_argument("--db", default="data/abel_learning.db")
    args = p.parse_args()
    if args.action == "import":
        result = import_txt(args.source)
    elif args.action == "plan":
        result = plan_rounds(_load(args.source))
    elif args.action == "request":
        result = generation_request(_load(args.source),
                                    json.loads(Path(args.plan).read_text(encoding="utf-8")),
                                    args.round, skill=args.skill)
    else:
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        entry = _round(plan, args.round)
        paper = json.loads(Path(args.paper).read_text(encoding="utf-8"))
        if args.action == "validate":
            validate_paper(paper, entry)
            result = {"status": "valid", "round_id": entry["id"], "question_count": 50}
        elif args.action == "student":
            result = student_view(paper, entry)
        else:
            answers = json.loads(Path(args.answers).read_text(encoding="utf-8"))
            result = grade(paper, entry, answers)
            if args.record:
                # Reuse the existing session -> error -> spaced-review -> snapshot chain.
                from learning_pipeline import run as learning_pipeline_run
                learning_pipeline_run([result], args.db)
    _write(args.out, result)
    print(args.out)


if __name__ == "__main__":
    main()
