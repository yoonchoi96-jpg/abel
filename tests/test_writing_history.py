from scripts.writing_history import error_summary, record_correction, vocabulary_summary


def sample(cache_key="abc"):
    return {
        "cache_key": cache_key,
        "original": "我维持了我的朋友。",
        "minimal_correction": "我维护了我的朋友。",
        "natural_version": "我一直维护着和朋友的关系。",
        "advanced_version": "我始终注重维护与朋友之间的关系。",
        "target_level": "HSK6",
        "register": "neutral",
        "version": "1.0.0",
        "prompt_version": "abel-writing-v1",
        "overall": {"severity": "major"},
        "hsk": {"target_level": "HSK6", "score": 72},
        "confidence": "high",
        "issues": [
            {
                "type": "word_choice",
                "severity": "major",
                "span": "维持",
                "correction": "维护",
                "rule": "verb-object compatibility",
            }
        ],
        "vocabulary_usage": [
            {"word": "维持", "word_id": "123", "status": "incorrect", "note_ko": "关系에는 보통 维护."},
            {"word": "维护", "word_id": "456", "status": "correct", "note_ko": ""},
        ],
    }


def test_record_is_idempotent(tmp_path):
    db = tmp_path / "learning.db"
    first = record_correction(sample(), db_path=db)
    second = record_correction(sample(), db_path=db)
    assert first == second
    assert error_summary(db_path=db)[0]["count"] == 1


def test_error_summary_and_vocab_summary(tmp_path):
    db = tmp_path / "learning.db"
    record_correction(sample(), db_path=db)
    errors = error_summary(db_path=db)
    vocab = vocabulary_summary(db_path=db)
    assert errors[0]["issue_type"] == "word_choice"
    assert vocab[0]["word"] == "维持"
    assert vocab[0]["incorrect_count"] == 1
