import base64
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import tempfile
from pathlib import Path
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastmcp.server.auth import StaticTokenVerifier
try:
    from gemini_tts_renderer import render_gemini_tts
    from drive_audio_uploader import DrivePublisher
except ModuleNotFoundError:
    from scripts.gemini_tts_renderer import render_gemini_tts
    from scripts.drive_audio_uploader import DrivePublisher

try:
    from hsk_evaluation_engine import finalize_review
    from hsk30_evaluation_engine import build_hsk30_llm_review_prompt, evaluate_hsk30_level6
    from writing_correction_engine import make_correction_envelope, validate_correction
    from multilingual_writing_engine import make_envelope as make_multilingual_envelope, validate_result as validate_multilingual_result
except ModuleNotFoundError:
    from scripts.hsk_evaluation_engine import finalize_review
    from scripts.hsk30_evaluation_engine import build_hsk30_llm_review_prompt, evaluate_hsk30_level6
    from scripts.writing_correction_engine import make_correction_envelope, validate_correction
    from scripts.multilingual_writing_engine import make_envelope as make_multilingual_envelope, validate_result as validate_multilingual_result

MCP_AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "")
MAX_LESSON_CHARS = 20000
MAX_QUESTIONS_JSON_CHARS = 2_000_000
MAX_REFERENCE_TEXT_CHARS = 200_000
MAX_QUESTIONS = 500

if MCP_AUTH_TOKEN:
    mcp_auth = StaticTokenVerifier(
        tokens={MCP_AUTH_TOKEN: {"sub": "abel-client", "client_id": "abel-client"}}
    )
    mcp = FastMCP("abel_mcp", auth=mcp_auth)
else:
    mcp = FastMCP("abel_mcp")


@mcp.tool()
def prepare_chinese_writing_correction(
    text: str,
    target_level: str = "HSK6",
    register: str = "neutral",
    context: str = "",
    known_words_json: str = "[]",
) -> dict:
    """Prepare a cached, machine-readable Chinese writing correction request.

    The tool deliberately returns a model-ready contract instead of silently
    inventing linguistic judgments. A Gemini/Gem education layer can execute the
    returned prompt and then validate the JSON with validate_chinese_writing_correction.
    """
    try:
        known_words = json.loads(known_words_json or "[]")
    except json.JSONDecodeError as exc:
        return {"status": "error", "message": f"known_words_json is invalid JSON: {exc}"}
    if not isinstance(known_words, list):
        return {"status": "error", "message": "known_words_json must decode to an array."}

    try:
        return make_correction_envelope(
            text,
            target_level=target_level,
            register=register,
            context=context,
            known_words=known_words,
        )
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}


@mcp.tool()
def validate_chinese_writing_correction(
    original: str,
    result_json: str,
) -> dict:
    """Validate a model-produced Abel writing-correction JSON contract."""
    try:
        result = json.loads(result_json)
    except json.JSONDecodeError as exc:
        return {"status": "error", "message": f"result_json is invalid JSON: {exc}"}

    errors = validate_correction(result, original)
    return {
        "status": "success" if not errors else "invalid",
        "valid": not errors,
        "errors": errors,
        "cache_key": result.get("cache_key") if isinstance(result, dict) else None,
    }


@mcp.tool()
def prepare_multilingual_writing_correction(
    text: str,
    language: str,
    target_level: str = "advanced",
    register: str = "neutral",
    context: str = "",
    known_words_json: str = "[]",
) -> dict:
    """Prepare a language-agnostic writing correction request for Gemini."""
    try:
        known_words = json.loads(known_words_json or "[]")
    except json.JSONDecodeError as exc:
        return {"status": "error", "message": f"known_words_json is invalid JSON: {exc}"}
    if not isinstance(known_words, list):
        return {"status": "error", "message": "known_words_json must decode to an array."}
    try:
        return make_multilingual_envelope(
            text, language=language, target_level=target_level,
            register=register, context=context, known_words=known_words,
        )
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}


@mcp.tool()
def validate_multilingual_writing_correction(
    original: str,
    result_json: str,
) -> dict:
    """Validate a multilingual writing-correction JSON contract."""
    try:
        result = json.loads(result_json)
    except json.JSONDecodeError as exc:
        return {"status": "error", "message": f"result_json is invalid JSON: {exc}"}
    errors = validate_multilingual_result(result, original)
    return {
        "status": "success" if not errors else "invalid",
        "valid": not errors,
        "errors": errors,
        "cache_key": result.get("cache_key") if isinstance(result, dict) else None,
    }


@mcp.tool()
def get_learning_history_summary(
    language: str = "zh-CN",
) -> dict:
    """Return the latest language-specific Abel learning snapshot for Gemini.

    Snapshot files are immutable-style exports and are safer for Cloud Run than
    relying on an ephemeral container SQLite database.
    """
    from pathlib import Path

    language = (language or "").strip()
    if not language or "/" in language or "\\" in language or language.startswith("."):
        return {"status": "error", "message": "Invalid language identifier."}

    path = Path(__file__).resolve().parent.parent / "data" / "learning_snapshots" / f"{language}.json"
    if not path.exists():
        return {
            "status": "not_found",
            "language": language,
            "message": "No language snapshot is currently available.",
        }

    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "error", "language": language, "message": str(exc)}

    return {
        "status": "success",
        "language": language,
        "schema_version": snapshot.get("schema_version"),
        "generated_at": snapshot.get("generated_at"),
        "stats": snapshot.get("stats", {}),
        "recurring_errors": snapshot.get("recurring_errors", []),
        "problematic_vocabulary": snapshot.get("problematic_vocabulary", []),
        "recent_corrections": snapshot.get("recent_corrections", []),
        "gemini_instructions": snapshot.get("gemini_instructions", {}),
    }


@mcp.tool()
def generate_lesson_audio(
    text: str,
    title: str = "",
    level: str = "HSK6",
    topic: str = "",
) -> dict:
    """Generate a Chinese listening lesson MP3 with Gemini TTS and save it directly to Google Drive.

    Production audio is Gemini TTS only. Apps Script and Google Cloud TTS are not
    used by this MCP tool.
    """
    text = (text or "").strip()
    if not text:
        return {"status": "error", "message": "Lesson text is required."}
    if len(text) > MAX_LESSON_CHARS:
        return {
            "status": "error",
            "message": f"Lesson text exceeds the {MAX_LESSON_CHARS}-character limit.",
        }

    current = datetime.now(ZoneInfo("Asia/Seoul"))
    date = current.strftime("%Y-%m-%d")
    time = current.strftime("%H%M%S")

    with tempfile.TemporaryDirectory(prefix="abel-mcp-tts-") as tmp:
        mp3_path = Path(tmp) / f"lesson_{date}_{time}.mp3"
        try:
            render_gemini_tts(
                text,
                mp3_path,
                voice=os.getenv("GEMINI_TTS_VOICE", "Kore"),
                model=os.getenv("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts"),
            )
        except Exception as exc:
            return {
                "status": "error",
                "stage": "gemini_tts",
                "message": f"Gemini TTS failed: {exc}",
            }

        try:
            publisher = DrivePublisher(os.getenv("ABEL_DRIVE_FOLDER_ID", ""))
            return publisher.publish_lesson(
                mp3_path,
                date=date,
                time=time,
                title=title,
                level=level,
                topic=topic,
                text=text,
            )
        except Exception as exc:
            return {
                "status": "error",
                "stage": "google_drive",
                "message": f"Google Drive upload failed: {exc}",
            }


@mcp.tool()
def evaluate_hsk_content(
    questions_json: str,
    transcript: str = "",
    reference_facts: str = "",
    expected_total: int = 0,
    expected_distribution_json: str = "",
) -> dict:
    """Run Abel's deterministic HSK exam QA and return the semantic-review prompt.

    questions_json must be a JSON array of question objects. Deterministic checks cover
    answer distribution, repeated answer runs, option-length/shape leakage, extreme-word
    distractor bias, duplicates, malformed options, and part ranges. Semantic checks are
    returned as a Gemini-ready review prompt rather than guessed by Python.
    """

    if len(questions_json) > MAX_QUESTIONS_JSON_CHARS:
        return {
            "status": "error",
            "message": f"questions_json exceeds the {MAX_QUESTIONS_JSON_CHARS}-character limit.",
        }

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

    if len(questions) > MAX_QUESTIONS:
        return {
            "status": "error",
            "message": f"questions_json exceeds the {MAX_QUESTIONS}-question limit.",
        }

    if len(transcript) > MAX_REFERENCE_TEXT_CHARS or len(reference_facts) > MAX_REFERENCE_TEXT_CHARS:
        return {
            "status": "error",
            "message": f"transcript and reference_facts are each limited to {MAX_REFERENCE_TEXT_CHARS} characters.",
        }

    if any(not isinstance(q, dict) for q in questions):
        return {
            "status": "error",
            "message": "Every question in questions_json must be a JSON object.",
        }

    expected_distribution = None
    if expected_distribution_json.strip():
        try:
            expected_distribution = json.loads(expected_distribution_json)
            if not isinstance(expected_distribution, dict):
                raise ValueError("expected_distribution_json must be a JSON object.")
        except (json.JSONDecodeError, ValueError) as exc:
            return {"status": "error", "message": f"expected_distribution_json is invalid: {exc}"}

    # Production HSK QA target: HSK 3.0 Level 6.
    # Full written mocks use 82 tasks: 1-40 listening, 41-80 reading, 81-82 writing.
    if expected_total not in (0, 82):
        return {
            "status": "error",
            "message": "HSK 3.0 Level 6 QA requires expected_total=82 (or omit it). Legacy 101-question HSK 2.0 layout is not supported by this production tool.",
        }

    report = evaluate_hsk30_level6(
        questions,
        expected_total=82,
        expected_answer_distribution=expected_distribution,
    )
    report["semantic_review_prompt"] = build_hsk30_llm_review_prompt(
        questions,
        transcript=transcript,
        reference_facts=reference_facts,
    )
    report["tool_status"] = "success"
    return report


@mcp.tool()
def finalize_hsk_review(
    deterministic_report_json: str,
    semantic_review_json: str = "",
) -> dict:
    """Apply Abel's final release gate to deterministic and Gemini semantic QA results.

    If semantic_review_json is omitted, the result stays in REVIEW/NOT_RUN rather
    than falsely passing. This keeps model-based review explicit and auditable.
    """
    try:
        deterministic_report = json.loads(deterministic_report_json)
        if not isinstance(deterministic_report, dict):
            raise ValueError("deterministic_report_json must be a JSON object.")
    except (json.JSONDecodeError, ValueError) as exc:
        return {"status": "error", "message": f"deterministic_report_json is invalid: {exc}"}

    semantic_review = None
    if semantic_review_json.strip():
        try:
            semantic_review = json.loads(semantic_review_json)
        except json.JSONDecodeError as exc:
            return {"status": "error", "message": f"semantic_review_json is invalid: {exc}"}

    return {
        "status": "success",
        "review": finalize_review(deterministic_report, semantic_review),
    }


@mcp.custom_route("/", methods=["GET"])
async def health(request: Request):
    return JSONResponse({
        "status": "online",
        "service": "Abel MCP Server",
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=port,
    )
