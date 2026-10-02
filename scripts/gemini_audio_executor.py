#!/usr/bin/env python3
"""Abel Gemini -> Apps Script audio executor.

Gemini decides when to call generate_lesson_audio.
This script executes that function locally and forwards the lesson
to the Abel Google Apps Script TTS endpoint.

Required environment variables:
  GEMINI_API_KEY
Optional:
  GEMINI_MODEL (default: gemini-3.8-flash)
  ABEL_APPS_SCRIPT_URL (overrides the default Apps Script deployment URL)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from google import genai


APPS_SCRIPT_URL = os.getenv(
    "ABEL_APPS_SCRIPT_URL",
    "https://script.google.com/macros/s/AKfycbyDPAMAbeZoyDOXI9VSHwQ-_DLqT4nA1ymiKi-LdrJNxozwKl240yu3Zz9f5WbDs18/exec",
)

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
KST = ZoneInfo("Asia/Seoul")


SYSTEM_PROMPT = """
You are Abel, the user's Chinese education automation agent.

Your job is to create Chinese listening lessons and send the finished
lesson to the Abel audio backend.

When the user asks for a listening lesson with audio:
1. Create the complete Chinese listening script yourself.
2. Choose an appropriate title, level, and topic.
3. Call generate_lesson_audio with the completed script.
4. Never ask the user to copy/paste JSON.
5. Never merely print a payload instead of calling the tool.
6. After the tool returns, report the result naturally and include the
   Google Drive file URL when one is returned.
7. Do NOT invent a date or time. Unless the user explicitly requests a
   specific date/time, omit date and time from the function call; the
   executor will use the current Korean date/time automatically.
8. For HSK6 requests, produce natural Mandarin suitable for HSK6
   listening practice.

The audio tool creates an MP3 with Google Cloud TTS and saves it in
the Abel Google Drive AUDIO folder.
"""


GENERATE_LESSON_AUDIO = {
    "type": "function",
    "name": "generate_lesson_audio",
    "description": (
        "Generate a Chinese listening lesson MP3 through the Abel "
        "Google Cloud TTS backend and save it to Google Drive."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["generate-lesson-audio"],
                "description": "Always use generate-lesson-audio.",
            },
            "text": {
                "type": "string",
                "description": "Complete Chinese listening script.",
            },
            "date": {
                "type": "string",
                "description": (
                    "Optional session date YYYY-MM-DD. Only provide this "
                    "when the user explicitly requests a specific date."
                ),
            },
            "time": {
                "type": "string",
                "description": (
                    "Optional session time HHMM. Only provide this when "
                    "the user explicitly requests a specific time."
                ),
            },
            "title": {
                "type": "string",
                "description": "Lesson title.",
            },
            "level": {
                "type": "string",
                "description": "Lesson level, e.g. HSK6.",
            },
            "topic": {
                "type": "string",
                "description": "Lesson topic.",
            },
        },
        "required": ["action", "text"],
    },
}


def now_kst() -> tuple[str, str]:
    now = datetime.now(KST)
    return now.strftime("%Y-%m-%d"), now.strftime("%H%M")


def call_apps_script(arguments: dict) -> dict:
    text = (arguments.get("text") or "").strip()
    if not text:
        return {"status": "error", "message": "Missing lesson text."}

    current_date, current_time = now_kst()

    # Date/time are only accepted when explicitly supplied by the user
    # through Gemini. Otherwise always use the current Korean time.
    payload = {
        "action": "generate-lesson-audio",
        "text": text,
        "date": arguments.get("date") or current_date,
        "time": arguments.get("time") or current_time,
        "title": arguments.get("title", ""),
        "level": arguments.get("level", ""),
        "topic": arguments.get("topic", ""),
    }

    try:
        # Apps Script ContentService returns 302 for the POST response.
        # Do not replay POST against the redirect target: it only accepts GET.
        first = requests.post(
            APPS_SCRIPT_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            allow_redirects=False,
            timeout=120,
        )

        location = first.headers.get("Location")
        if first.status_code in (301, 302, 303, 307, 308) and location:
            response = requests.get(location, timeout=120)
        else:
            response = first

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

    except requests.RequestException as exc:
        return {"status": "error", "message": f"HTTP request failed: {exc}"}


def execute_function(name: str, arguments: dict) -> dict:
    if name != "generate_lesson_audio":
        return {"status": "error", "message": f"Unknown function: {name}"}

    arguments = dict(arguments)
    arguments["action"] = "generate-lesson-audio"
    return call_apps_script(arguments)


def run(prompt: str) -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is not set.")

    client = genai.Client(api_key=api_key)
    tools = [GENERATE_LESSON_AUDIO]

    interaction = client.interactions.create(
        model=MODEL,
        input=SYSTEM_PROMPT + "\n\nUSER REQUEST:\n" + prompt,
        tools=tools,
    )

    for _ in range(5):
        calls = [
            step for step in interaction.steps
            if step.type == "function_call"
        ]

        if not calls:
            print(interaction.output_text or "작업이 완료되었습니다.")
            return

        results = []
        for call in calls:
            print(
                f"[ABEL] executing {call.name}({json.dumps(call.arguments, ensure_ascii=False)})",
                file=sys.stderr,
            )

            result = execute_function(call.name, call.arguments)

            print(
                f"[ABEL] result: {json.dumps(result, ensure_ascii=False)}",
                file=sys.stderr,
            )

            results.append({
                "type": "function_result",
                "name": call.name,
                "call_id": call.id,
                "result": [{
                    "type": "text",
                    "text": json.dumps(result, ensure_ascii=False),
                }],
            })

        interaction = client.interactions.create(
            model=MODEL,
            previous_interaction_id=interaction.id,
            input=results,
            tools=tools,
        )

    raise SystemExit("Maximum function-call rounds exceeded.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Abel Gemini audio executor")
    parser.add_argument("prompt", nargs="+", help="User request for Gemini")
    args = parser.parse_args()
    run(" ".join(args.prompt))


if __name__ == "__main__":
    main()
