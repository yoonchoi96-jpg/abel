import json

from scripts.writing_correction_engine import (
    PROMPT_VERSION,
    build_writing_prompt,
    correction_cache_key,
    make_correction_envelope,
    validate_correction,
)


def test_cache_key_is_stable_and_input_sensitive():
    a = correction_cache_key("나는 중국어를 공부한다.")
    b = correction_cache_key("나는 중국어를 공부한다.")
    c = correction_cache_key("나는 중국어를 열심히 공부한다.")
    assert a == b
    assert a != c


def test_prompt_preserves_four_correction_layers():
    prompt = build_writing_prompt("虽然很累，但是我还是去了。")
    assert "minimal_correction" in prompt
    assert "natural_version" in prompt
    assert "advanced_version" in prompt
    assert PROMPT_VERSION in prompt


def test_envelope_contains_known_word_context_and_cache_key():
    envelope = make_correction_envelope(
        "这个政策维持了社会稳定。",
        target_level="HSK6",
        known_words=[{"word_id": 1, "word": "维持"}],
    )
    assert envelope["status"] == "ready_for_llm"
    assert envelope["known_word_count"] == 1
    assert len(envelope["cache_key"]) == 64
    assert "维持" in envelope["prompt"]


def _valid_result(original):
    return {
        "schema_version": "abel.writing.v1",
        "engine": "Abel Chinese Writing Correction Engine",
        "version": "1.0.0",
        "original": original,
        "overall": {"status": "revise", "summary_ko": "어휘 선택을 수정할 수 있습니다.", "severity": "minor"},
        "versions": {
            "minimal_correction": original,
            "natural_version": original,
            "advanced_version": original,
        },
        "issues": [],
        "vocabulary_usage": [],
        "hsk": {
            "target_level": "HSK6",
            "writing_quality": "meets",
            "score": 80,
            "score_scale": "0-100",
            "rationale_ko": "",
        },
        "confidence": "high",
    }


def test_validation_accepts_contract():
    original = "我每天学习中文。"
    assert validate_correction(_valid_result(original), original) == []


def test_validation_rejects_changed_original():
    original = "我每天学习中文。"
    result = _valid_result(original)
    result["original"] = "我每天学习英文。"
    assert validate_correction(result, original)


def test_validation_rejects_bad_score():
    original = "我每天学习中文。"
    result = _valid_result(original)
    result["hsk"]["score"] = 101
    assert validate_correction(result, original)


def test_validation_rejects_missing_version():
    original = "我每天学习中文。"
    result = _valid_result(original)
    del result["versions"]["advanced_version"]
    assert validate_correction(result, original)
