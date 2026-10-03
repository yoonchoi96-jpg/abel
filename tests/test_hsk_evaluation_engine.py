import json

from scripts.hsk_evaluation_engine import build_llm_review_prompt, evaluate_exam


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
