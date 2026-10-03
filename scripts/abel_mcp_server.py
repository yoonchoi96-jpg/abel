import json
import os
import requests
from fastmcp import FastMCP
from starlette.requests import Request

from hsk_evaluation_engine import build_llm_review_prompt, evaluate_exam

mcp = FastMCP("abel_mcp")

APPS_SCRIPT_URL = os.environ["ABEL_APPS_SCRIPT_URL"]
MCP_AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "")


@mcp.tool()
def generate_lesson_audio(
    text: str,
    title: str = "",
    level: str = "HSK6",
    topic: str = "",
) -> dict:
    """Generate a Chinese listening lesson MP3 and save it to Abel Google Drive."""

    payload = {
        "action": "generate-lesson-audio",
        "text": text,
        "title": title,
        "level": level,
        "topic": topic,
    }

    response = requests.post(
        APPS_SCRIPT_URL,
        json=payload,
        headers={"Content-Type": "application/json"},
        allow_redirects=False,
        timeout=120,
    )

    location = response.headers.get("Location")

    if response.status_code in (301, 302, 303, 307, 308) and location:
        response = requests.get(location, timeout=120)

    if response.status_code != 200:
        return {
            "status": "error",
            "http_status": response.status_code,
            "message": response.text[:3000],
        }

    try:
        return response.json()
    except ValueError:
        return {
            "status": "error",
            "message": "Apps Script returned non-JSON data.",
            "raw_response": response.text[:3000],
        }


@mcp.tool()
def evaluate_hsk_content(
    questions_json: str,
    transcript: str = "",
    reference_facts: str = "",
    expected_total: int = 0,
) -> dict:
    """Run Abel's deterministic HSK exam QA and return the semantic-review prompt.

    questions_json must be a JSON array of question objects. Deterministic checks cover
    answer distribution, repeated answer runs, option-length/shape leakage, extreme-word
    distractor bias, duplicates, malformed options, and part ranges. Semantic checks are
    returned as a Gemini-ready review prompt rather than guessed by Python.
    """

    try:
        questions = json.loads(questions_json)
    except json.JSONDecodeError as exc:
        return {
            "status": "error",
            "message": f"questions_json is invalid JSON: {exc}",
        }

    if not isinstance(questions, list):
        return {
            "status": "error",
            "message": "questions_json must decode to a JSON array.",
        }

    report = evaluate_exam(
        questions,
        expected_total=expected_total or None,
    )
    report["semantic_review_prompt"] = build_llm_review_prompt(
        questions,
        transcript=transcript,
        reference_facts=reference_facts,
    )
    report["status"] = "success"
    return report


@mcp.custom_route("/", methods=["GET"])
def health(request: Request):
    return {
        "status": "online",
        "service": "Abel MCP Server",
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=port,
    )
