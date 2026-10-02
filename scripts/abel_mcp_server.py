import os
import requests
from fastmcp import FastMCP

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


@mcp.custom_route("/", methods=["GET"])
def health():
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
