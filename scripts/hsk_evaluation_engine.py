#!/usr/bin/env python3
"""Deterministic HSK mock-exam QA engine.

This module turns recurring expert-review findings into machine-checkable signals.
It intentionally does NOT pretend to judge semantic correctness. LLM review remains
responsible for ambiguity, naturalness, factual accuracy, and pedagogical quality.

Input question shape:
{
  "number": 1,
  "part": "listening|reading|writing",
  "stem": "...",
  "options": ["A ...", "B ...", "C ...", "D ..."],
  "answer": "A",
  "transcript": "..."
}
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, asdict
from typing import Any


EXTREME_MARKERS = (
    "完全", "彻底", "毫无", "任何", "所有", "全部", "绝对", "必然",
    "从不", "从未", "永远", "唯一", "全面", "必须", "无法", "零", "最优",
    "取之不尽", "无可辩驳",
)

PART_LIMITS = {
    "listening": (1, 50),
    "reading": (51, 100),
    "writing": (101, 101),
}


@dataclass
class Finding:
    rule_id: str
    severity: str
    message: str
    question_numbers: list[int]


def _answer_letter(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip().upper()
    m = re.search(r"\b([ABCD])\b", s)
    return m.group(1) if m else (s if s in "ABCD" else None)


def _option_text(option: Any) -> str:
    text = str(option).strip()
    # Accept common HSK option labels: A. text, A、text, A) text, or Atext.
    return re.sub(r"^[\s【\[]*[ABCD](?:[\.、:：\)）\s]+|(?=[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]))", "", text, flags=re.I)


def _chinese_len(text: str) -> int:
    return len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text or ""))


def _normalized(text: str) -> str:
    text = str(text or "").strip()
    text = re.sub(r"^[ABCD][\.、:：\)）]\s*", "", text, flags=re.I)
    return re.sub(r"\s+", "", text)


def _finding(rule_id: str, severity: str, message: str, nums: list[int]) -> Finding:
    return Finding(rule_id, severity, message, sorted(set(nums)))


def evaluate_exam(
    questions: list[dict[str, Any]],
    *,
    expected_answer_distribution: dict[str, int] | None = None,
    expected_total: int | None = None,
) -> dict[str, Any]:
    """Run deterministic structural/statistical QA over an exam."""

    findings: list[Finding] = []
    answers: list[tuple[int, str]] = []
    longest_answer_hits: list[int] = []
    extreme_wrong: list[int] = []
    extreme_right: list[int] = []
    malformed: list[int] = []
    duplicate_stems: dict[str, list[int]] = {}
    duplicate_options: dict[int, list[str]] = {}
    option_shape_leaks: list[int] = []
    one_option_trivial: list[int] = []

    for q in questions:
        n = int(q.get("number", 0) or 0)
        answer = _answer_letter(q.get("answer"))
        options = q.get("options") or []
        if not n or answer not in "ABCD" or len(options) < 4:
            malformed.append(n)
            continue

        answers.append((n, answer))
        texts = [_option_text(x) for x in options[:4]]

        normalized_options = [_normalized(x) for x in texts]
        duplicate_option_values = [
            value for value, count in Counter(normalized_options).items() if count > 1
        ]
        if duplicate_option_values:
            duplicate_options[n] = duplicate_option_values

        stem_key = _normalized(q.get("stem", ""))
        if stem_key:
            duplicate_stems.setdefault(stem_key, []).append(n)

        lengths = [_chinese_len(x) for x in texts]
        max_len = max(lengths)
        if lengths.count(max_len) == 1 and lengths[ord(answer) - ord("A")] == max_len:
            longest_answer_hits.append(n)

        extreme_flags = [any(marker in x for marker in EXTREME_MARKERS) for x in texts]
        if extreme_flags[ord(answer) - ord("A")]:
            extreme_right.append(n)
        elif any(extreme_flags):
            extreme_wrong.append(n)

        # A structural leak: one option has a different broad ending/shape.
        endings = [re.sub(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", "汉", x) for x in texts]
        shape_counts = Counter(endings)
        if len(shape_counts) == 2 and max(shape_counts.values()) == 3:
            odd = next(k for k, v in shape_counts.items() if v == 1)
            if endings[ord(answer) - ord("A")] == odd:
                option_shape_leaks.append(n)

        # If one option is dramatically shorter than all others, flag for review.
        sorted_lengths = sorted(lengths)
        if sorted_lengths[-1] - sorted_lengths[0] >= max(8, math.ceil(sorted_lengths[-1] * 0.45)):
            one_option_trivial.append(n)

    if malformed:
        findings.append(_finding("STRUCT_MALFORMED", "error",
                                 "Questions must contain number, answer A-D, and four options.", malformed))

    dist = Counter(a for _, a in answers)
    if expected_answer_distribution is not None and dict(dist) != dict(expected_answer_distribution):
        findings.append(_finding(
            "ANSWER_DISTRIBUTION_MISMATCH", "warning",
            f"Actual answer distribution is {dict(sorted(dist.items()))}; expected {expected_answer_distribution}.",
            [n for n, _ in answers],
        ))

    if expected_total is not None and len(questions) != expected_total:
        findings.append(_finding(
            "QUESTION_COUNT", "error",
            f"Expected {expected_total} questions but received {len(questions)}.",
            [n for n, _ in answers],
        ))

    for part, (lo, hi) in PART_LIMITS.items():
        nums = [int(q.get("number", 0) or 0) for q in questions if q.get("part") == part]
        if nums:
            if min(nums) < lo or max(nums) > hi:
                findings.append(_finding("PART_RANGE", "error",
                    f"{part} question numbers fall outside {lo}-{hi}.", nums))

    if answers:
        run = 1
        max_run = 1
        run_nums = []
        current_nums = [answers[0][0]]
        for (_, a_prev), (n_cur, a_cur) in zip(answers, answers[1:]):
            if a_cur == a_prev:
                run += 1
                current_nums.append(n_cur)
            else:
                if run > max_run:
                    max_run, run_nums = run, current_nums[:]
                run = 1
                current_nums = [n_cur]
        if run > max_run:
            max_run, run_nums = run, current_nums[:]
        if max_run >= 3:
            findings.append(_finding("ANSWER_RUN", "warning",
                f"Same answer letter appears {max_run} times consecutively.", run_nums))

    if extreme_wrong and not extreme_right:
        findings.append(_finding("EXTREME_WORD_BIAS", "warning",
            f"Extreme/absolute wording appears in wrong options but never in correct options ({len(extreme_wrong)} questions).",
            extreme_wrong))
    elif extreme_wrong:
        ratio = len(extreme_wrong) / max(1, len(extreme_wrong) + len(extreme_right))
        if ratio >= 0.8:
            findings.append(_finding("EXTREME_WORD_BIAS", "warning",
                f"Extreme wording is concentrated in wrong options ({ratio:.0%}).",
                extreme_wrong + extreme_right))

    if answers:
        ratio = len(longest_answer_hits) / len(answers)
        if ratio >= 0.30:
            findings.append(_finding("LONGEST_ANSWER_BIAS", "warning",
                f"The correct option is uniquely longest in {len(longest_answer_hits)}/{len(answers)} questions ({ratio:.0%}).",
                longest_answer_hits))

    if option_shape_leaks:
        findings.append(_finding("OPTION_SHAPE_LEAK", "warning",
            "The correct option has a unique surface/grammar shape among otherwise parallel options.",
            option_shape_leaks))

    if one_option_trivial:
        findings.append(_finding("OPTION_LENGTH_LEAK", "warning",
            "At least one option is dramatically different in length; inspect for test-taking clues.",
            one_option_trivial))

    duplicate_stem_groups = [nums for nums in duplicate_stems.values() if len(nums) > 1]
    duplicate_option_questions = sorted(duplicate_options)
    if duplicate_stem_groups or duplicate_option_questions:
        nums = [n for group in duplicate_stem_groups for n in group] + duplicate_option_questions
        findings.append(_finding("DUPLICATE_CONTENT", "error",
            "Duplicate stems or duplicate options within a single question detected.", nums))

    severity_score = {"error": 25, "warning": 8, "info": 0}
    penalty = min(100, sum(severity_score[f.severity] for f in findings))
    status = "FAIL" if any(f.severity == "error" for f in findings) else ("REVIEW" if findings else "PASS")

    return {
        "engine": "Abel HSK Evaluation Engine",
        "version": "1.1.0",
        "status": status,
        "score": max(0, 100 - penalty),
        "metrics": {
            "question_count": len(questions),
            "answer_distribution": dict(sorted(dist.items())),
            "max_answer_run": max_run if answers else 0,
            "correct_is_longest_ratio": round(len(longest_answer_hits) / max(1, len(answers)), 3),
            "extreme_wrong_count": len(extreme_wrong),
            "extreme_correct_count": len(extreme_right),
        },
        "findings": [asdict(f) for f in findings],
        "llm_review_required": [
            "answer uniqueness / multiple valid answers",
            "semantic distractor quality",
            "Chinese naturalness and collocation",
            "transcript-question-answer consistency",
            "factual accuracy",
            "HSK difficulty and paraphrase depth",
            "explanation accuracy",
        ],
    }


def finalize_review(
    deterministic_report: dict[str, Any],
    semantic_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Combine deterministic QA with an externally produced semantic-review JSON.

    Abel does not invent semantic judgments. It only validates the review contract
    and converts the two QA layers into one machine-readable release gate.
    """
    result = {
        "gate": "FAIL" if deterministic_report.get("status") == "FAIL" else "PASS",
        "deterministic_status": deterministic_report.get("status", "UNKNOWN"),
        "semantic_status": "NOT_RUN",
        "score": deterministic_report.get("score", 0),
        "release_ready": False,
        "critical_issues": [],
        "global_issues": [],
    }

    if result["gate"] == "FAIL":
        return result

    if semantic_review is None:
        result["gate"] = "REVIEW"
        result["semantic_status"] = "NOT_RUN"
        return result

    if not isinstance(semantic_review, dict):
        result["gate"] = "FAIL"
        result["semantic_status"] = "INVALID"
        result["critical_issues"] = ["semantic_review must be a JSON object."]
        return result

    required = ("pass", "score", "critical_issues", "question_reviews", "global_issues")
    missing = [key for key in required if key not in semantic_review]
    if missing:
        result["gate"] = "FAIL"
        result["semantic_status"] = "INVALID"
        result["critical_issues"] = [f"Missing semantic-review fields: {', '.join(missing)}"]
        return result

    semantic_pass = bool(semantic_review.get("pass"))
    semantic_score = semantic_review.get("score")
    if not isinstance(semantic_score, (int, float)) or not 0 <= semantic_score <= 100:
        result["gate"] = "FAIL"
        result["semantic_status"] = "INVALID"
        result["critical_issues"] = ["semantic_review.score must be a number from 0 to 100."]
        return result

    result["semantic_status"] = "PASS" if semantic_pass else "REVISE"
    result["score"] = min(float(deterministic_report.get("score", 0)), float(semantic_score))
    result["critical_issues"] = list(semantic_review.get("critical_issues") or [])
    result["global_issues"] = list(semantic_review.get("global_issues") or [])

    if not semantic_pass or result["critical_issues"]:
        result["gate"] = "REVIEW"
    else:
        result["gate"] = "PASS"

    result["release_ready"] = result["gate"] == "PASS"
    return result


def build_llm_review_prompt(
    questions: list[dict[str, Any]],
    *,
    transcript: str = "",
    reference_facts: str = "",
) -> str:
    """Build the semantic QA prompt distilled from expert/Claude review findings."""

    payload = {
        "questions": questions,
        "transcript": transcript,
        "reference_facts": reference_facts,
    }
    return """You are Abel's expert HSK mock-exam reviewer.

Review the supplied Chinese HSK6 mock-exam material. This is an adversarial QA pass:
do not reward a question merely because it looks plausible.

MANDATORY CHECKS
1. ANSWER UNIQUENESS: reject any item where two options can reasonably be correct under
   the stem, grammar, transcript, or normal contemporary Mandarin usage.
2. DISTRACTOR QUALITY: distractors must be plausible but decisively wrong. Do not use
   absurd absolutes, obvious exaggeration, or unrelated options as easy signals.
3. SURFACE LEAKAGE: reject items where the answer can be identified from option length,
   grammar shape, part of speech, sentence completeness, copied wording, or a single
   unusually distinctive token.
4. PARAPHRASE DEPTH: reject questions whose correct option simply repeats a distinctive
   phrase from the transcript/passage when the intended skill is comprehension.
5. TRANSCRIPT/EXPLANATION ALIGNMENT: every answer and explanation must be supported by
   the supplied text. Distinguish 'not mentioned' from 'contradicted'.
6. NATURAL CHINESE: judge collocation, syntax, register, and actual contemporary usage.
   A sentence being technically grammatical is not sufficient if the intended context
   makes it unnatural.
7. FACTUAL ACCURACY: flag scientific, historical, technical, numerical, naming, and
   causal claims that require external verification. Do not invent verification.
8. EXAM DESIGN: avoid repeating the same error type excessively. Avoid questions that
   can be solved from one blank/one token when the task is intended to test integrated
   comprehension.
9. EXPLANATIONS: explanations must discuss the actual current option wording, not an
   earlier revision. For each wrong option, give a concrete reason when explanation is
   requested.
10. REGRESSION: if a revision fixed one defect but created ambiguity, leakage, factual
    error, or a new grammar problem, flag the regression.

IMPORTANT: Do not simplify HSK6 content merely to make it easier. Difficulty should come
from vocabulary, syntax, inference, information structure, and genuine paraphrase—not
from obscure trivia or intentionally bad Chinese.

Return JSON only:
{
  "pass": true,
  "score": 0,
  "critical_issues": [],
  "question_reviews": [
    {
      "number": 0,
      "status": "pass|revise|reject",
      "answer": "A",
      "issues": [],
      "recommended_fix": ""
    }
  ],
  "global_issues": [],
  "factual_verification_needed": []
}

""" + json.dumps(payload, ensure_ascii=False, indent=2)
