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
    "https://script.google.com/macros/s/AKfycby2uN5ArGnOML3fHpEcP5X4wmMv8lsVgg1kuu8ZmRKwkUYvGxtj2tIDyf2FtyAgDdkA/exec",
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

CHINESE SPOKEN-PROSODY RULES:
The text passed to generate_lesson_audio is the FINAL recording script.
Write for a native Mandarin speaker to say aloud, not for silent reading.

A. Preserve HSK difficulty
- Keep genuine HSK6 vocabulary, syntax, discourse structure, and information density.
- "Natural spoken Chinese" must NOT mean easier Chinese.
- Do not replace advanced vocabulary merely to make speech easier.

B. Sentence rhythm
- Deliberately vary sentence length: short response, medium sentence,
  then longer sentence where appropriate.
- Avoid strings of sentences with identical grammatical structure.
- Avoid overly long written-style sentences when the same meaning can be
  expressed as two natural spoken units.
- Use punctuation to reflect real phrasing and breath groups.
- Prefer normal Chinese punctuation: ， 。 ？ ！
- Do not use [pause], (pause), stage directions, SSML tags, or other
  meta-instructions in the script.
- Do not use repeated ellipses …… as a mechanical pause device.
- Do not insert commas everywhere. Punctuation must reflect meaning and
  natural phrasing.

C. Spoken discourse
- In dialogues, use a small amount of authentic discourse marking when
  the context supports it: 嗯、其实、不过、你看、我觉得、怎么说呢、
  也就是说、说实话、对了.
- These expressions are optional, not mandatory.
- Never add fillers simply to make the text "sound human".
- Do not repeat the same filler mechanically.
- Avoid stereotyped gender-based speech patterns.
- Speakers should differ through role, attitude, sentence length, and
  response style rather than caricature.

D. Natural interaction
- Dialogue should contain realistic reactions, confirmations,
  clarifications, additions, or mild self-correction when appropriate.
- Not every reply should be a perfectly complete textbook sentence.
- Limited forms such as "不是，我的意思是……" may be used only when
  they genuinely fit the situation; do not manufacture hesitation.
- Do not let naturalness obscure information needed to answer a question.

E. Non-dialogue formats
- Interviews, lectures, announcements, reports, and explanatory passages
  should sound like their real-world genre.
- Use discourse markers such as 首先、不过、实际上、换句话说、
  值得注意的是 only when they naturally belong to the genre.
- Formal genres should not be forced into casual conversation.

F. HSK exam listening mode
- Default to clear, realistic, moderately paced Mandarin.
- Natural prosody is required, but exaggerated acting is not.
- Avoid excessive emotional performance, slang, dialect, sound effects,
  or pronunciation tricks unless the exercise explicitly targets them.
- Keep dates, numbers, names, locations, causal relationships, contrasts,
  and other answer-bearing details acoustically easy to identify.
- Do not place unnecessary fillers immediately before or inside key facts.
- Do not intentionally make the script harder to parse merely to simulate
  "native speed".

G. Native-speaker rhythm pass
Before calling generate_lesson_audio, silently rewrite the script once in your
head as if you were a native Mandarin speaker preparing to record it.

- Prefer natural information chunks rather than perfectly balanced written sentences.
- Let sentence boundaries occur where a speaker would naturally complete a thought.
- Use occasional short standalone sentences to reset rhythm.
- Mix sentence openings and avoid repeated "主语 + 谓语 + 宾语" patterns.
- In dialogue, allow concise replies, confirmations, and natural follow-ups instead
  of making every turn equally polished.
- In explanatory speech, connect ideas with natural transitions rather than stacking
  formal written clauses.
- Use commas only for meaningful phrasing; do not create a comma after every clause.
- Avoid artificial "performance" cues. The punctuation must be ordinary Chinese prose.
- Do not deliberately add pauses, fillers, slang, or hesitation just for realism.
- Never weaken HSK6 vocabulary, syntax, inference, or information density.
- Preserve every fact needed to answer the listening questions.

H. TTS-specific quality gate
Immediately before the tool call, verify:
1. The first sentence does not sound like a written essay opening unless the genre requires it.
2. Adjacent sentences do not share the same length and syntactic template repeatedly.
3. There is a natural alternation of short, medium, and longer utterances.
4. Dialogue turns are not uniformly long.
5. Discourse markers are sparse and purposeful.
6. Key dates, numbers, names, contrasts, causes, and conclusions remain isolated enough
   to hear clearly.
7. No SSML, stage directions, bracketed cues, mechanical ellipses, or meta commentary.
8. The final text can be sent directly to TTS without any backend rewriting.

The generated text must already be the final spoken version. Do not rely on
the audio backend to repair unnatural Chinese.

I. Do not over-naturalize
Natural spoken Mandarin is not the same as casual chat.
For lectures, interviews, reports, and exam-style passages, retain the appropriate
register. Do not turn formal HSK6 material into social-media speech.
Do not insert "嗯", "其实", "你看", etc. unless a real speaker would plausibly need them.

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
