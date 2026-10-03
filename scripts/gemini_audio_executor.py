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

from audio_style_profiles import __doc__ as AUDIO_STYLE_PROFILES


APPS_SCRIPT_URL = os.getenv(
    "ABEL_APPS_SCRIPT_URL",
    "https://script.google.com/macros/s/AKfycby2uN5ArGnOML3fHpEcP5X4wmMv8lsVgg1kuu8ZmRKwkUYvGxtj2tIDyf2FtyAgDdkA/exec",
)

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
KST = ZoneInfo("Asia/Seoul")


SYSTEM_PROMPT = """
AUDIO DELIVERY PROFILE POLICY
Abel audio delivery profiles.

These profiles are the canonical style formulas used by lesson generation and
spoken-language QA. A lesson has exactly one primary delivery_mode unless a
multi-speaker mode is explicitly selected.

Modes:
- conversational_dialogue: two native speakers, asymmetric turns, real reactions,
  confirmations, questions, clarification, mild disagreement; standard Mandarin,
  natural everyday educated speech; HSK6 density preserved.
- interview: interviewer + expert; interviewer turns compact, expert turns developed;
  natural follow-up questions; no scripted equal-length turns.
- news_report: professional Mandarin news delivery; information-dense, controlled,
  formal vocabulary acceptable; spoken segmentation; restrained broadcast contour.
- announcement: official public-information delivery; concise, orderly, clear,
  information-first; no chatty fillers.
- lecture_explanation: educated professor/expert explaining aloud; logical exposition,
  examples, reformulation, contrast/consequence; conversational enough to sound spoken,
  not an essay read verbatim.
- narrative_story: natural storyteller; temporal progression, event focus, short
  reactions/evaluations; expressive but restrained.
- formal_informational: calm professional presenter/expert; relatively formal lexical
  register; spoken phrasing and intelligible segmentation.
- casual_explanation: one educated Chinese adult casually explaining an interesting
  topic to a friend/classmate; relaxed but standard Mandarin; no announcer/teacher style.

Voice formulas:
- single-speaker modes use Gemini TTS or the existing Chirp backend according to
  backend policy.
- conversational_dialogue uses Gemini TTS multi-speaker with:
    男 -> Puck
    女 -> Kore
  Both use cmn-CN and natural conversational delivery.
- interview uses the same two-voice architecture unless a single-speaker interview
  is explicitly requested.
- news_report may use a broadcast-style single voice.
- lecture_explanation/formal_informational use a calm educated single voice.
- announcement uses an official clear single voice.
- narrative_story uses a natural storytelling single voice.
- casual_explanation uses a relaxed conversational single voice.

All modes:
- never translate or rewrite the final script during TTS;
- never add English;
- preserve HSK6 vocabulary, syntax, facts and answer-bearing details;
- no SSML/stage directions in the lesson text;
- naturalness comes from information structure, phrasing and turn design, not filler.
"""


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
- Treat punctuation as semantic phrasing, not decoration: a comma should usually
  correspond to a meaningful information boundary, while a full stop should often
  close a complete thought rather than merely end a long written sentence.
- Do not use [pause], (pause), stage directions, SSML tags, or other
  meta-instructions in the script.
- Do not use repeated ellipses …… as a mechanical pause device.
- Do not insert commas everywhere. Punctuation must reflect meaning and
  natural phrasing.
- Avoid creating a sequence of sentences that all end with the same neutral
  declarative cadence. Vary statement, explanation, contrast, question, response,
  and short follow-up structures when the genre permits.

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
- Use occasional short standalone sentences to reset rhythm, especially after a dense
  sentence carrying several facts.
- Mix sentence openings and avoid repeated "主语 + 谓语 + 宾语" patterns.
- Use authentic Mandarin information structure when appropriate: topic-comment,
  time/place framing, contrast-before-conclusion, cause-before-result, and short
  afterthoughts can sound more natural than repeatedly starting with a named subject.
- Do not force every sentence into the same "setup → comma → conclusion" shape.
- When a key fact is followed by a consequence or interpretation, consider a short
  follow-up sentence rather than attaching everything to one long clause.
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

I. REGISTER-AWARE SPOKEN MANDARIN GENERATION
First classify the lesson internally into one primary delivery mode:
1. CONVERSATIONAL DIALOGUE — everyday but educated Mandarin; concise turns,
   natural topic shifts, confirmations, clarifications, mild disagreement,
   ellipsis/subject omission where context makes the referent obvious.
2. INTERVIEW — spontaneous but articulate; interviewer questions can be compact,
   interviewee answers can develop an idea across several sentence lengths.
3. ANNOUNCEMENT / NOTICE — concise, orderly, information-first; not chatty.
4. NEWS / REPORT — information-dense broadcast Mandarin; controlled and relatively
   formal, but still spoken in phrasing and sentence segmentation.
5. LECTURE / EXPLANATION — planned spoken exposition; explicit logical links,
   examples, reformulation, contrast and consequence; do not turn it into an essay.
6. NARRATIVE / STORY — temporal progression, event focus, occasional short reactions
   or evaluative follow-ups; preserve narrative clarity.
7. FORMAL INFORMATIONAL — relatively written vocabulary and syntax are acceptable,
   but the segmentation must still sound like a person delivering information aloud.

Then apply these linguistic principles:
- Spoken Mandarin frequently relies on discourse context rather than repeating the
  grammatical subject. Omit or replace repeated subjects when the referent is clear;
  do NOT omit them when ambiguity would affect comprehension.
- Use topic-comment structure naturally when it improves information flow. The topic
  may be a time, place, object, issue, or previously mentioned entity rather than a
  repeated personal subject.
- Prefer information structure that moves from given/contextual information toward
  new or contrastive information. Put the answer-bearing/new information in the
  structurally prominent part of the sentence.
- Use short follow-up clauses for reactions, consequences, clarification, or evaluation
  when they would naturally be separate speech units. Do not turn every idea into one
  syntactically balanced sentence.
- Allow natural spoken constructions such as 其实、不过、所以、这样一来、后来、
  结果、也就是说、换句话说、你可以理解为 when they perform a real discourse
  function. They are not required in every passage.
- Sentence-final particles such as 吧、呢、啊 should be rare and genre-appropriate.
  Never sprinkle them merely to create a "Chinese-sounding" effect.
- Avoid textbook-like repetition of explicit subjects, identical transition phrases,
  and identical sentence-final patterns.
- Avoid deliberately adding fragments, fillers, contractions, slang, or colloquialisms.
  Naturalness comes primarily from information structure and turn design, not decoration.
- Preserve advanced HSK6 constructions such as long modifier chains, 把/被 structures,
  complex complements, relative clauses, conditionals, concessions, causal chains,
  nominalization, and abstract noun phrases when the content calls for them.
- Do not force every HSK6 sentence into a short spoken form. Real educated speech can
  contain long syntactically complex sentences; what matters is that the information
  hierarchy and phrasing are intelligible.
- Avoid "written-language vocabulary + conversational filler" as a fake hybrid.
  Register must be internally coherent.

HSK6 SPOKEN-NATURALITY TARGET:
The ideal script should sound like an educated native speaker explaining, reporting,
discussing, or responding to the topic aloud — NOT like a casual social-media post and
NOT like a written article read verbatim.

GENRE-SPECIFIC BALANCE:
- Dialogue: prioritize interactional realism, but keep vocabulary and reasoning at HSK6.
- Lecture: prioritize logical exposition and natural spoken segmentation; do not casualize.
- Report/news: retain formal lexical choices and dense facts; use spoken sentence boundaries.
- Narrative: prioritize temporal/event progression and natural reaction structure.
- Announcement: prioritize concise, explicit, easily recoverable information.
- Interview: let turns have asymmetric lengths and different discourse functions.
- Formal passage: preserve literary/formal register where needed, but avoid unnecessarily
  nested clauses that would be difficult for an actual speaker to deliver.

J. FINAL LINGUISTIC PATTERN CHECK
Before generating audio, silently inspect the whole script for these measurable patterns:
- Three or more adjacent sentences beginning with the same grammatical frame.
- Three or more adjacent sentences with nearly identical length and punctuation shape.
- Repeated explicit subject when the referent is already obvious.
- Repeated discourse marker at the same position.
- Repeated sentence-final pattern with no discourse reason.
- Long sentence containing multiple independent propositions that would naturally be
  delivered as separate thoughts.
- Excessive one-clause fragmentation that sounds artificially "written for TTS".
- A dialogue in which every turn is complete, equally long, and equally polished.
- A formal passage contaminated by unnecessary casual fillers.
If any pattern appears, revise the structure rather than merely changing words.

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



SPEECH_QA_PROMPT = """
You are the final Chinese spoken-language QA editor for an HSK6 listening lesson.

Your reference for "natural" is professionally produced HSK listening audio:
clear and controlled, but not metronomic. The goal is a skilled native Mandarin
speaker communicating meaning, with phrasing driven by information structure.
Do NOT imitate casual chat or add acting.

Review the candidate script BEFORE it is sent to TTS.

CORE QA:
- Genuine HSK6 vocabulary, syntax, inference, and information density remain intact.
- Natural spoken Mandarin for the genre, not an essay being read aloud.
- Vary sentence length, opening structure, and information density.
- Avoid repeated adjacent syntactic templates, especially repeated "主语 + 谓语 + 宾语".
- Put sentence boundaries at completed thoughts, not arbitrary written-clause boundaries.
- Use punctuation to support semantic phrasing, not to manufacture pauses.
- Dialogue turns should vary naturally in length; short confirmations and follow-ups are
  useful when the situation calls for them.
- Discourse markers and fillers are sparse and purposeful.
- Dates, numbers, names, contrasts, causes, and conclusions remain clear.
- No SSML, stage directions, bracketed cues, meta-commentary, or mechanical ellipses.
- Formal genres retain their register.
- Advanced vocabulary is not simplified for TTS.

NATURAL-CADENCE QA:
- Do NOT make every sentence equally polished, symmetrical, or complete.
- Do NOT make every sentence the same approximate length.
- Avoid a sequence of similarly shaped clauses separated by commas.
- When one written sentence contains multiple independent thoughts, split it into two
  spoken sentences when that improves comprehension and rhythm without changing meaning.
- Conversely, do not fragment sentences merely to create artificial "human" pauses.
- Keep dense noun phrases and modifier chains intact when they carry HSK6 meaning;
  do not simplify advanced syntax just to shorten the audio.
- For long sentences, make the information hierarchy obvious: context first, then the
  central claim or event, then supporting detail or consequence. Do not give every clause
  equal prosodic weight.
- In dialogue, let the second speaker react to the semantic focus of the first speaker;
  avoid producing two consecutive turns with the same grammatical rhythm.
- Prefer meaningful information chunks: setup -> development -> key detail -> consequence
  or conclusion, when appropriate to the genre.
- Allow occasional short standalone sentences to reset the listener after a dense sentence.
- Avoid mechanically repeating the same transition at the start of successive sentences.
- Do not sprinkle 嗯、其实、你看、对了 or similar fillers merely to imitate speech.
- Do not use punctuation as a hidden prosody control system; keep ordinary Chinese prose.
- In dialogue, reactions should answer what the previous speaker actually said rather than
  functioning as generic textbook turn-taking.
- For formal passages, preserve controlled broadcast/educational delivery rather than
  forcing conversational slang or exaggerated emotion.
- For exam listening, keep answer-bearing facts acoustically prominent through clean
  phrasing and surrounding structure, not unnatural pauses or repetition.

REGISTER CHECK:
- Identify the script's likely genre before judging its naturalness.
- Do not penalize formal vocabulary merely because it is not casual speech.
- Do penalize formal prose that sounds like an article being read verbatim when the same
  register could be delivered more naturally through spoken segmentation.
- In dialogue, check subject omission, topic continuity, reaction relevance, and asymmetric
  turn length rather than counting fillers.
- In lecture/report formats, check information hierarchy, logical transitions, and spoken
  segmentation rather than demanding conversational slang.
- Check that advanced HSK6 syntax remains present where it carries meaning.
- Naturalness must come from Mandarin discourse organization, not from adding "human-like"
  filler words.

LINGUISTIC PATTERN CHECK:
- Flag three or more adjacent sentences with the same grammatical opening.
- Flag repeated explicit subjects when context already supplies the referent.
- Flag repeated transition markers in the same syntactic position.
- Flag repeated sentence-final forms without a semantic reason.
- Flag over-balanced sentences where each clause has the same syntactic weight.
- Flag fragmented prose where short sentences appear at suspiciously regular intervals.
- Flag dialogue where every turn has the same grammatical completeness and length.
- Flag "formal vocabulary + casual filler" mixtures that do not belong to one coherent
  register.

FINAL "READ ALOUD" TEST:
Imagine a native speaker recording the script in one take.
Reject or revise it if the imagined reading feels like:
1. a written essay being read word-for-word;
2. a metronome with identical sentence contours;
3. a chain of equally long textbook sentences;
4. dialogue where every turn has the same polished shape; or
5. a script padded with fillers solely to sound human.

Pass it when the imagined reading feels clear, information-driven, naturally chunked,
and professionally recorded, while still sounding recognizably like HSK listening material.

Return ONLY valid JSON:
{
  "pass": true or false,
  "score": 0-100,
  "issues": ["short concrete issue", "..."],
  "revised_text": "full final script if changes are needed, otherwise the original script"
}

PASS means ready for TTS, not merely grammatically correct.
If score is below 88, set pass=false.
If there is no meaningful problem, preserve the original script exactly.
"""

def review_script(client, script: str, title: str, level: str, topic: str) -> dict:
    prompt = (
        SPEECH_QA_PROMPT
        + "\n\nTITLE: " + title
        + "\nLEVEL: " + level
        + "\nTOPIC: " + topic
        + "\n\nCANDIDATE SCRIPT:\n" + script
    )
    review = client.interactions.create(model=MODEL, input=prompt)
    raw = (review.output_text or "").strip()
    result = None
    candidates = [raw]
    fence = "```"
    if fence in raw:
        candidates.extend(
            part.strip().removeprefix("json").strip()
            for part in raw.split(fence)
            if "{" in part
        )
    decoder = json.JSONDecoder()
    for candidate in candidates:
        start = candidate.find("{")
        if start < 0:
            continue
        try:
            parsed, _ = decoder.raw_decode(candidate[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            result = parsed
            break
    if result is None:
        return {
            "pass": False,
            "score": 0,
            "issues": ["Speech QA returned invalid JSON."],
            "revised_text": script,
        }

    if not isinstance(result, dict):
        return {
            "pass": False,
            "score": 0,
            "issues": ["Speech QA returned an invalid object."],
            "revised_text": script,
        }

    result.setdefault("pass", False)
    result.setdefault("score", 0)
    result.setdefault("issues", [])
    result.setdefault("revised_text", script)

    if not str(result.get("revised_text") or "").strip():
        result["revised_text"] = script
    return result


def prepare_audio_arguments(client, arguments: dict) -> tuple[dict, dict]:
    prepared = dict(arguments)
    script = (prepared.get("text") or "").strip()
    if not script:
        return prepared, {
            "pass": False,
            "score": 0,
            "issues": ["Missing lesson text."],
            "revised_text": "",
        }

    # One repair pass followed by one verification pass.
    qa = review_script(
        client, script,
        str(prepared.get("title") or ""),
        str(prepared.get("level") or ""),
        str(prepared.get("topic") or ""),
    )

    if not qa.get("pass", False):
        revised = str(qa.get("revised_text") or script).strip()
        if revised and revised != script:
            prepared["text"] = revised
            qa2 = review_script(
                client, revised,
                str(prepared.get("title") or ""),
                str(prepared.get("level") or ""),
                str(prepared.get("topic") or ""),
            )
            if qa2.get("pass", False):
                qa = qa2
            else:
                qa = {
                    "pass": False,
                    "score": qa2.get("score", 0),
                    "issues": qa2.get("issues", []),
                    "revised_text": revised,
                }
    return prepared, qa


def execute_function(name: str, arguments: dict, client=None) -> dict:
    if name != "generate_lesson_audio":
        return {"status": "error", "message": f"Unknown function: {name}"}

    arguments = dict(arguments)
    arguments["action"] = "generate-lesson-audio"

    if client is not None:
        arguments, qa = prepare_audio_arguments(client, arguments)
        print(
            f"[ABEL] speech QA: score={qa.get('score')} pass={qa.get('pass')} "
            f"issues={json.dumps(qa.get('issues', []), ensure_ascii=False)}",
            file=sys.stderr,
        )
        if not qa.get("pass", False):
            return {
                "status": "error",
                "stage": "speech_qa",
                "message": "Lesson script did not pass spoken-Mandarin QA after one repair pass.",
                "score": qa.get("score", 0),
                "issues": qa.get("issues", []),
                "revised_text": arguments.get("text", ""),
            }

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

            result = execute_function(call.name, call.arguments, client=client)

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

# Speech QA parser hardened for provider-formatted JSON responses.
