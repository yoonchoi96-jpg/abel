"""Regression tests for the personal TOEIC adapter (no private wordbook committed)."""
import json
import pytest

from scripts.toeic_learning import (
    import_txt, plan_rounds, generation_request, validate_paper,
    student_view, grade, QUOTAS, SCHEMA, PAPER_SCHEMA
)
from scripts.learning_router import resolve_learning_route


def make_corpus(count=600):
    words = []
    for i in range(1, count + 1):
        priority = "P3" if i <= 20 else "P4" if i <= 100 else "P5"
        words.append({
            "id": f"toeic-vocab-{i:04d}", "original_rank": i,
            "expression": f"term_{i}", "meaning_ko": f"뜻_{i}",
            "priority": priority, "latest_review": 2 if i <= 20 else 1,
            "eligible_for_answer_key": i % 19 != 0,
            "source_location": f"IMG_{i}", "language": "en-US",
        })
    return {"schema_version": SCHEMA, "language": "en-US", "count": count, "words": words}


def test_corrected_txt_import_and_review_priority(tmp_path):
    content = (
        "순위\t등급\t영어 표현\t한국어 뜻\t회독 표시\tY(1회)\tB(2회)\tR(3회)\tG(4회)\t원본 / 위치\t검토\t판독\t교정 제안\n"
        "1\tP2\treprimand\t질책하다\t노랑 파랑 빨강\t✓\t✓\t✓\t\t3886 R8\t수정완료\t상\t\n"
        "2\tP5\tmystery\t미확인\t\t\t\t\t\t3900 #1\t영어확인\t하\t\n"
    )
    src = tmp_path / "wordbook.txt"
    src.write_text(content, encoding="utf-8")
    data = import_txt(src)
    assert data["count"] == 2
    assert data["words"][0]["id"] == "toeic-vocab-0001"
    assert data["words"][0]["priority"] == "P2"
    assert data["words"][0]["eligible_for_answer_key"]
    assert not data["words"][1]["eligible_for_answer_key"]


def test_bad_priority_and_duplicate_rank_blocked(tmp_path):
    src = tmp_path / "bad.txt"
    line = "1\tP1\talpha\t알파\t\t✓\t\t\t\t3890 #1\t\t상\t\n"
    src.write_text(line, encoding="utf-8")
    with pytest.raises(ValueError, match="priority/mark"):
        import_txt(src)
    src.write_text(line.replace("P1", "P4") * 2, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate original rank"):
        import_txt(src)


def make_paper(entry):
    word_ids = entry["eligible_vocab_ids"][:50]
    qs = []
    idx = 0
    for section, n in QUOTAS.items():
        for _ in range(n):
            idx += 1
            qs.append({
                "id": f"q{idx}", "section": section,
                "stem": f"Original English question {idx}",
                "options": {"A": "one", "B": "two", "C": "three", "D": "four"},
                "answer": "B", "vocab_id": word_ids[idx-1],
                "explanation_ko": "문맥상 B가 정답이며 나머지는 적절하지 않음",
            })
    return {"schema_version": PAPER_SCHEMA, "round_id": entry["id"], "questions": qs}


def test_distribution_and_round_requests():
    corpus = make_corpus()
    plan = plan_rounds(corpus)
    rounds = plan["rounds"]
    assert len(rounds) == 10
    assigned = [id for r in rounds for id in r["study_vocab_ids"]]
    assert len(assigned) == len(set(assigned)) == corpus["count"]
    assert all(len(r["eligible_vocab_ids"]) >= 50 for r in rounds)
    assert set(rounds[0]["extra_review_ids"]).issubset(
        {w["id"] for w in corpus["words"] if w["priority"] in ("P1", "P2", "P3")})
    req = generation_request(corpus, plan, 1)
    assert req["status"] == "awaiting_external_question_authoring"
    assert req["expected_result_shape"]["schema_version"] == PAPER_SCHEMA
    for skill, expected in (("speaking", 11), ("writing", 8)):
        assert len(generation_request(corpus, plan, 1, skill=skill)["expected_result_shape"]["tasks"]) == expected
    assert "audio_script" in generation_request(corpus, plan, 1, skill="listening")["expected_result_shape"]


def test_validate_student_and_grade():
    entry = plan_rounds(make_corpus())["rounds"][0]
    paper = make_paper(entry)
    assert validate_paper(paper, entry)
    exposed = student_view(paper, entry)
    assert all("answer" not in q and "vocab_id" not in q and "explanation_ko" not in q
               for q in exposed["questions"])
    answers = {f"q{i}": "B" for i in range(1, 51)}
    answers["q1"] = "A"
    result = grade(paper, entry, answers)
    assert (result["total"], result["correct"], result["score"]) == (50, 49, 98.0)
    assert result["language"] == "en-US"
    assert result["kind"] == "reading"
    assert result["resource_id"] == "toeic-personal-wordbook"
    assert result["results"][0]["question_id"] == paper["questions"][0]["vocab_id"]
    assert result["results"][0]["error_type"] == "meaning"


def test_bad_question_and_wrong_source_blocked():
    entry = plan_rounds(make_corpus())["rounds"][0]
    paper = make_paper(entry)
    paper["questions"][1]["vocab_id"] = paper["questions"][0]["vocab_id"]
    with pytest.raises(ValueError, match="duplicated"):
        validate_paper(paper, entry)
    paper = make_paper(entry)
    paper["questions"][0]["answer"] = "E"
    with pytest.raises(ValueError, match="answer"):
        validate_paper(paper, entry)
    paper = make_paper(entry)
    paper["questions"][15]["section"] = "vocabulary"
    with pytest.raises(ValueError, match="quota"):
        validate_paper(paper, entry)


def test_english_route_without_breaking_chinese():
    assert resolve_learning_route(language="en-US", skill="reading", level="TOEIC").parts == (
        "English", "Reading", "TOEIC")
    assert resolve_learning_route(language="zh-CN", skill="writing", level="HSK6").parts == (
        "Chinese", "Writing", "HSK6")
