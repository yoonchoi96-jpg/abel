#!/usr/bin/env python3
"""Bridge existing Abel deterministic engines to education tasks."""
from __future__ import annotations
from typing import Any
from education_task_adapters import TASKS
from multilingual_writing_engine import make_envelope as writing_envelope
from adaptive_learning_plan import build_plan
from hsk_evaluation_engine import evaluate_exam
from listening_practice_engine import score as score_listening
from reading_practice_engine import score as score_reading
from writing_practice_engine import prepare as prepare_writing
from mock_test_engine import aggregate as aggregate_mock
from error_review_engine import build_review

def prepare_local(task_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    if task_type not in TASKS:
        raise ValueError(f"unsupported_task:{task_type}")
    if task_type == "chinese_writing_correction":
        return writing_envelope(
            payload["text"], language=payload.get("language","zh-CN"),
            target_level=payload.get("target_level","HSK6"),
            register=payload.get("register","neutral"),
            context=payload.get("context",""), known_words=payload.get("known_words")
        )
    if task_type == "adaptive_learning_plan":
        return build_plan(payload.get("candidates", payload.get("items", [])), payload.get("limits"))
    if task_type == "hsks_exam_qa":
        questions=payload.get("questions")
        if not isinstance(questions,list) or not questions:
            raise ValueError("hsks_exam_qa requires source-backed questions")
        return evaluate_exam(
            questions,
            expected_answer_distribution=payload.get("expected_answer_distribution"),
            expected_total=payload.get("expected_total"),
        )
    if task_type == "listening_practice":
        return score_listening(payload["resource"], payload.get("answers", {}))
    if task_type == "reading_practice":
        return score_reading(payload["resource"], payload.get("answers", {}))
    if task_type == "writing_practice":
        return prepare_writing(payload["resource"])
    if task_type == "mock_test":
        return aggregate_mock(payload["mock"], payload["units"], payload.get("results", []))
    if task_type == "error_review":
        return build_review(payload.get("results", []))
    return {"task_type":task_type,"payload":payload,"execution":"provider_required"}

def local_available(task_type: str) -> bool:
    return task_type in {
        "chinese_writing_correction","adaptive_learning_plan","hsks_exam_qa",
        "listening_practice","reading_practice","writing_practice","mock_test","error_review",
    }
