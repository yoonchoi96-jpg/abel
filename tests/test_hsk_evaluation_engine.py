import json

from scripts.hsk_evaluation_engine import build_llm_review_prompt, evaluate_exam, finalize_review


def test_distribution_and_answer_run():
    qs = [
        {"number": 1, "part": "listening", "stem": "x", "options": ["A甲", "B乙", "C丙", "D丁"], "answer": "A"},
        {"number": 2, "part": "listening", "stem": "y", "options": ["A甲", "B乙", "C丙", "D丁"], "answer": "A"},
        {"number": 3, "part": "listening", "stem": "z", "options": ["A甲", "B乙", "C丙", "D丁"], "answer": "A"},
    ]
    report = evaluate_exam(qs)
    assert report["metrics"]["answer_distribution"] == {"A": 3}
    assert report["metrics"]["max_answer_run"] == 3
    assert report["status"] == "REVIEW"


def test_extreme_wording_bias():
    qs = []
    for i in range(1, 5):
        qs.append({
            "number": i, "part": "listening", "stem": str(i),
            "options": ["A完全正确", "B普通表述", "C一般情况", "D另一种说法"],
            "answer": "B",
        })
    report = evaluate_exam(qs)
    assert any(f["rule_id"] == "EXTREME_WORD_BIAS" for f in report["findings"])


def test_longest_answer_bias():
    qs = []
    for i in range(1, 5):
        qs.append({
            "number": i, "part": "reading", "stem": str(i),
            "options": ["A短", "B这是一个明显更长的正确答案", "C中等", "D普通"],
            "answer": "B",
        })
    report = evaluate_exam(qs)
    assert any(f["rule_id"] == "LONGEST_ANSWER_BIAS" for f in report["findings"])


def test_llm_prompt_contains_claude_derived_rules():
    prompt = build_llm_review_prompt([{
        "number": 1, "stem": "x",
        "options": ["A", "B", "C", "D"], "answer": "A"
    }])
    assert "ANSWER UNIQUENESS" in prompt
    assert "PARAPHRASE DEPTH" in prompt
    assert "REGRESSION" in prompt


def test_repeated_option_set_across_questions_is_not_duplicate_content():
    qs = [
        {"number": 1, "part": "listening", "stem": "first", "options": ["A甲", "B乙", "C丙", "D丁"], "answer": "A"},
        {"number": 2, "part": "listening", "stem": "second", "options": ["A甲", "B乙", "C丙", "D丁"], "answer": "B"},
    ]
    report = evaluate_exam(qs)
    assert not any(f["rule_id"] == "DUPLICATE_CONTENT" for f in report["findings"])


def test_duplicate_option_inside_question_is_flagged():
    qs = [
        {"number": 1, "part": "listening", "stem": "x", "options": ["A甲", "B甲", "C丙", "D丁"], "answer": "A"},
    ]
    report = evaluate_exam(qs)
    assert any(f["rule_id"] == "DUPLICATE_CONTENT" for f in report["findings"])


def test_duplicate_stems_across_questions_are_flagged():
    qs = [
        {"number": 1, "part": "listening", "stem": "same", "options": ["A甲", "B乙", "C丙", "D丁"], "answer": "A"},
        {"number": 2, "part": "listening", "stem": "same", "options": ["A甲", "B乙", "C丙", "D丁"], "answer": "B"},
    ]
    report = evaluate_exam(qs)
    assert any(f["rule_id"] == "DUPLICATE_CONTENT" for f in report["findings"])


def test_malformed_question_is_fail():
    report = evaluate_exam([{"number": 1, "part": "listening", "stem": "x", "options": ["A", "B"], "answer": "A"}])
    assert report["status"] == "FAIL"
    assert any(f["rule_id"] == "STRUCT_MALFORMED" for f in report["findings"])


def test_expected_total_and_part_range():
    qs = [
        {"number": 1, "part": "reading", "stem": "x", "options": ["A甲", "B乙", "C丙", "D丁"], "answer": "A"},
    ]
    report = evaluate_exam(qs, expected_total=2)
    assert any(f["rule_id"] == "QUESTION_COUNT" for f in report["findings"])
    assert any(f["rule_id"] == "PART_RANGE" for f in report["findings"])


def _passing_deterministic_report():
    return evaluate_exam([
        {"number": 1, "part": "listening", "stem": "x", "options": ["A甲", "B乙", "C丙", "D丁"], "answer": "A"},
    ])


def test_finalize_review_requires_semantic_pass_for_release():
    deterministic = _passing_deterministic_report()
    missing = finalize_review(deterministic)
    assert missing["gate"] == "REVIEW"
    assert not missing["release_ready"]

    semantic = {
        "pass": True,
        "score": 96,
        "critical_issues": [],
        "question_reviews": [
            {"number": 1, "status": "pass", "issues": []},
        ],
        "global_issues": [],
        "factual_verification_needed": [],
    }
    passed = finalize_review(deterministic, semantic)
    assert passed["gate"] == "PASS"
    assert passed["release_ready"]
    assert passed["score"] == 96


def test_finalize_review_rejects_critical_semantic_issue():
    semantic = {
        "pass": True,
        "score": 96,
        "critical_issues": ["Question 7 has two valid answers."],
        "question_reviews": [
            {"number": 1, "status": "pass", "issues": []},
        ],
        "global_issues": [],
        "factual_verification_needed": [],
    }
    result = finalize_review(_passing_deterministic_report(), semantic)
    assert result["gate"] == "REVIEW"
    assert not result["release_ready"]


def test_compact_chinese_option_labels_are_normalized():
    qs = [
        {"number": 1, "part": "listening", "stem": "x", "options": ["A甲", "B甲", "C丙", "D丁"], "answer": "A"},
    ]
    report = evaluate_exam(qs)
    assert any(f["rule_id"] == "DUPLICATE_CONTENT" for f in report["findings"])


def test_english_option_starting_with_a_is_not_stripped():
    qs = [
        {"number": 1, "part": "listening", "stem": "x", "options": ["Apple", "Book", "Cat", "Dog"], "answer": "A"},
    ]
    report = evaluate_exam(qs)
    assert report["metrics"]["question_count"] == 1


def test_finalize_review_does_not_release_deterministic_review_status():
    semantic = {
        "pass": True,
        "score": 99,
        "critical_issues": [],
        "question_reviews": [],
        "global_issues": [],
        "factual_verification_needed": [],
    }
    deterministic = _passing_deterministic_report()
    deterministic["status"] = "REVIEW"
    result = finalize_review(deterministic, semantic)
    assert result["gate"] == "REVIEW"
    assert not result["release_ready"]


def test_finalize_review_rejects_string_boolean_pass():
    semantic = {
        "pass": "false",
        "score": 99,
        "critical_issues": [],
        "question_reviews": [],
        "global_issues": [],
        "factual_verification_needed": [],
    }
    result = finalize_review(_passing_deterministic_report(), semantic)
    assert result["semantic_status"] == "INVALID"
    assert not result["release_ready"]


def test_finalize_review_requires_full_question_review_coverage():
    deterministic = evaluate_exam([
        {"number": 1, "part": "listening", "stem": "x", "options": ["A甲", "B乙", "C丙", "D丁"], "answer": "A"},
        {"number": 2, "part": "listening", "stem": "y", "options": ["A甲", "B乙", "C丙", "D丁"], "answer": "B"},
    ])
    semantic = {
        "pass": True,
        "score": 99,
        "critical_issues": [],
        "question_reviews": [
            {"number": 1, "status": "pass", "issues": []},
        ],
        "global_issues": [],
        "factual_verification_needed": [],
    }
    result = finalize_review(deterministic, semantic)
    assert result["semantic_status"] == "INVALID"
    assert "coverage" in result["critical_issues"][0].lower()
    assert not result["release_ready"]


def test_finalize_review_blocks_unresolved_factual_verification():
    deterministic = _passing_deterministic_report()
    semantic = {
        "pass": True,
        "score": 99,
        "critical_issues": [],
        "question_reviews": [
            {"number": 1, "status": "pass", "issues": []},
        ],
        "global_issues": [],
        "factual_verification_needed": ["Verify the historical date."],
    }
    result = finalize_review(deterministic, semantic)
    assert result["gate"] == "REVIEW"
    assert not result["release_ready"]


def test_duplicate_question_number_and_option_count_are_failures():
    report = evaluate_exam([
        {"number": 1, "part": "listening", "stem": "x", "options": ["A甲", "B乙", "C丙", "D丁", "E戊"], "answer": "A"},
        {"number": 1, "part": "listening", "stem": "y", "options": ["A甲", "B乙", "C丙", "D丁"], "answer": "B"},
    ])
    assert report["status"] == "FAIL"
    rules = {f["rule_id"] for f in report["findings"]}
    assert "DUPLICATE_QUESTION_NUMBER" in rules
    assert "OPTION_COUNT" in rules


def test_answer_run_uses_question_number_order():
    qs = [
        {"number": 3, "part": "listening", "stem": "z", "options": ["A甲", "B乙", "C丙", "D丁"], "answer": "A"},
        {"number": 1, "part": "listening", "stem": "x", "options": ["A甲", "B乙", "C丙", "D丁"], "answer": "A"},
        {"number": 2, "part": "listening", "stem": "y", "options": ["A甲", "B乙", "C丙", "D丁"], "answer": "A"},
    ]
    report = evaluate_exam(qs)
    assert report["metrics"]["max_answer_run"] == 3
    assert any(f["rule_id"] == "ANSWER_RUN" for f in report["findings"])


def test_question_number_conversion_is_safe():
    report = evaluate_exam([
        {"number": "not-a-number", "part": "listening", "stem": "x", "options": ["A", "B", "C", "D"], "answer": "A"},
    ])
    assert report["status"] == "FAIL"
    assert any(f["rule_id"] == "STRUCT_MALFORMED" for f in report["findings"])


def test_finalize_review_rejects_forged_minimal_deterministic_report():
    result = finalize_review(
        {"status": "PASS", "score": 100},
        {
            "pass": True,
            "score": 100,
            "critical_issues": [],
            "question_reviews": [],
            "global_issues": [],
            "factual_verification_needed": [],
        },
    )
    assert result["gate"] == "FAIL"
    assert result["semantic_status"] == "NOT_RUN"
    assert not result["release_ready"]


def test_finalize_review_requires_exact_question_review_numbers():
    deterministic = _passing_deterministic_report()
    semantic = {
        "pass": True,
        "score": 99,
        "critical_issues": [],
        "question_reviews": [
            {"number": 999, "status": "pass", "issues": []},
        ],
        "global_issues": [],
        "factual_verification_needed": [],
    }
    result = finalize_review(deterministic, semantic)
    assert result["semantic_status"] == "INVALID"
    assert not result["release_ready"]


def test_hsk6_part_layout_is_enforced_for_full_exam():
    qs = []
    for number in range(1, 101):
        part = "listening" if number <= 50 else "reading"
        qs.append({
            "number": number,
            "part": part,
            "stem": str(number),
            "options": ["A甲", "B乙", "C丙", "D丁"],
            "answer": "A",
        })
    qs.append({
        "number": 101,
        "part": "reading",
        "stem": "writing should be separate",
        "options": ["A甲", "B乙", "C丙", "D丁"],
        "answer": "B",
    })
    report = evaluate_exam(qs, expected_total=101)
    assert report["status"] == "FAIL"
    assert any(f["rule_id"] == "HSK6_PART_LAYOUT" for f in report["findings"])


def test_hsk6_part_layout_accepts_exact_full_exam_numbering():
    qs = []
    for number in range(1, 102):
        if number <= 50:
            part = "listening"
        elif number <= 100:
            part = "reading"
        else:
            part = "writing"
        qs.append({
            "number": number,
            "part": part,
            "stem": str(number),
            "options": ["A甲", "B乙", "C丙", "D丁"],
            "answer": "A",
        })
    report = evaluate_exam(qs, expected_total=101)
    assert not any(f["rule_id"] == "HSK6_PART_LAYOUT" for f in report["findings"])


def test_bracketed_option_labels_are_normalized():
    qs = [
        {
            "number": 1,
            "part": "listening",
            "stem": "x",
            "options": ["【A】甲", "[B]乙", "C、丙", "D:丁"],
            "answer": "A",
        },
    ]
    report = evaluate_exam(qs)
    assert report["status"] == "PASS"


def test_question_number_fraction_is_rejected():
    report = evaluate_exam([
        {"number": 1.5, "part": "listening", "stem": "x", "options": ["A", "B", "C", "D"], "answer": "A"},
    ])
    assert report["status"] == "FAIL"
    assert any(f["rule_id"] == "STRUCT_MALFORMED" for f in report["findings"])


def test_question_number_boolean_is_rejected():
    report = evaluate_exam([
        {"number": True, "part": "listening", "stem": "x", "options": ["A", "B", "C", "D"], "answer": "A"},
    ])
    assert report["status"] == "FAIL"
    assert any(f["rule_id"] == "STRUCT_MALFORMED" for f in report["findings"])
