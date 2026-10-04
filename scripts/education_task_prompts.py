#!/usr/bin/env python3
"""Deterministic task-specific teaching prompts for provider-backed Abel tasks."""
from __future__ import annotations
from typing import Any

SCHEMA="abel.education.task-prompt.v1"

def build(task_type:str, payload:dict[str,Any])->dict[str,Any]:
    if task_type=="translation":
        source=payload.get("text") or payload.get("input","")
        source_lang=payload.get("source_language","auto")
        target_lang=payload.get("target_language","ko-KR")
        return _out(task_type, f"""Translate the source faithfully from {source_lang} to {target_lang}.
Preserve meaning, register, names, numbers, and formatting. Do not add facts.
Return the translation, alternatives only when ambiguity is material, and a brief Korean explanation of important choices.
Source:
{source}""")
    if task_type=="chinese_explanation":
        text=payload.get("text") or payload.get("input","")
        level=payload.get("target_level","HSK6")
        return _out(task_type, f"""Teach this Chinese material at {level} level.
Explain grammar, vocabulary, collocations, nuance, and why the wording works.
Use Korean for explanations and Chinese for examples. Do not invent rules.
Material:
{text}""")
    if task_type=="vocabulary_review":
        words=payload.get("words") or payload.get("items") or []
        level=payload.get("target_level","HSK6")
        return _out(task_type, f"""Create a high-difficulty vocabulary review for {level}.
Use only the supplied vocabulary. Test meaning, collocation, context, and discrimination between near-synonyms.
Do not lower difficulty or invent learner history.
Vocabulary:
{words}""")
    if task_type=="listening_transcript_analysis":
        transcript=payload.get("transcript","")
        return _out(task_type, f"""Analyze this listening transcript for language learning.
Identify key vocabulary, grammar, discourse structure, implied meaning, and likely listening traps.
Explain in Korean. Quote only short excerpts from the supplied transcript.
Transcript:
{transcript}""")
    if task_type=="speaking_feedback":
        text=payload.get("transcript") or payload.get("text","")
        level=payload.get("target_level","HSK6")
        return _out(task_type, f"""Evaluate this spoken Chinese response at {level}.
Separate grammatical correctness from naturalness and register. Give pronunciation or fluency observations only when supported by supplied audio metadata or transcript.
Provide corrected and more natural versions with Korean explanations.
Response:
{text}""")
    if task_type=="current_facts_research":
        question=payload.get("question") or payload.get("text","")
        return _out(task_type, f"""Research the current factual question below.
Prefer authoritative and recent sources. Clearly separate verified facts from uncertainty.
Question:
{question}""")
    return {"schema_version":SCHEMA,"task_type":task_type,"prompt":payload.get("prompt") or payload.get("input") or payload.get("text","")}

def _out(task_type:str,prompt:str)->dict[str,Any]:
    return {"schema_version":SCHEMA,"task_type":task_type,"prompt":prompt}

def supported()->set[str]:
    return {"translation","chinese_explanation","vocabulary_review","listening_transcript_analysis","speaking_feedback","current_facts_research"}
