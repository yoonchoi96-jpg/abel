import json
import importlib
import asyncio


def _server(monkeypatch):
    monkeypatch.setenv("ABEL_APPS_SCRIPT_URL", "https://example.com/abel-apps-script")
    import scripts.abel_mcp_server as server
    return importlib.reload(server)


def test_generate_lesson_audio_rejects_empty_and_oversized_input(monkeypatch):
    server = _server(monkeypatch)
    assert server.generate_lesson_audio("").get("status") == "error"
    oversized = server.generate_lesson_audio("甲" * (server.MAX_LESSON_CHARS + 1))
    assert oversized.get("status") == "error"
    assert "limit" in oversized.get("message", "").lower()


def test_evaluate_hsk_content_enforces_request_size_and_question_count(monkeypatch):
    server = _server(monkeypatch)

    oversized = server.evaluate_hsk_content("x" * (server.MAX_QUESTIONS_JSON_CHARS + 1))
    assert oversized.get("status") == "error"

    questions = [
        {
            "number": i,
            "part": "listening",
            "stem": str(i),
            "options": ["A甲", "B乙", "C丙", "D丁"],
            "answer": "A",
        }
        for i in range(1, server.MAX_QUESTIONS + 2)
    ]
    result = server.evaluate_hsk_content(json.dumps(questions, ensure_ascii=False))
    assert result.get("status") == "error"
    assert "question" in result.get("message", "").lower()


def test_finalize_hsk_review_rejects_non_object_deterministic_report(monkeypatch):
    server = _server(monkeypatch)
    result = server.finalize_hsk_review(json.dumps([]))
    assert result.get("status") == "error"


def test_health_returns_json_response(monkeypatch):
    server = _server(monkeypatch)
    response = asyncio.run(server.health(None))
    assert response.status_code == 200
    assert b'"status":"online"' in response.body
