#!/usr/bin/env python3
"""Task adapters: deterministic construction of source-backed education payloads."""
from __future__ import annotations
from typing import Any
from education_task_prompts import build as build_prompt

TASKS=(
    "chinese_writing_correction","translation","chinese_explanation","vocabulary_review",
    "hsks_exam_qa","adaptive_learning_plan","listening_transcript_analysis","speaking_feedback",
    "listening_practice","reading_practice","writing_practice","mock_test","error_review",
)

def prepare(task_type:str,payload:dict[str,Any])->dict[str,Any]:
    if task_type not in TASKS: raise ValueError(f"unsupported_task:{task_type}")
    if not isinstance(payload,dict): raise ValueError("payload must be an object")
    p=dict(payload)
    p["task_type"]=task_type
    if task_type in {"translation","chinese_explanation","vocabulary_review","listening_transcript_analysis","speaking_feedback","current_facts_research"} and not p.get("prompt"):
        p["prompt"]=build_prompt(task_type,p)["prompt"]
    return p

def require_source(payload:dict[str,Any])->None:
    if payload.get("source_of_truth") not in (None,"Abel"):
        raise ValueError("source_of_truth must be Abel")
