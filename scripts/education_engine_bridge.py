#!/usr/bin/env python3
"""Bridge existing Abel engines to task adapters without invoking external APIs."""
from __future__ import annotations
from typing import Any, Callable
from education_task_adapters import TASKS
from multilingual_writing_engine import make_envelope as writing_envelope

LOCAL_PREPARERS={"chinese_writing_correction": writing_envelope}

def prepare_local(task_type:str,payload:dict[str,Any])->dict[str,Any]:
    if task_type not in TASKS: raise ValueError(f"unsupported_task:{task_type}")
    fn=LOCAL_PREPARERS.get(task_type)
    if fn is not None:
        return fn(payload["text"], target_level=payload.get("target_level","HSK6"), register=payload.get("register","neutral"), context=payload.get("context"), known_words=payload.get("known_words"))
    return {"task_type":task_type,"payload":payload,"execution":"provider_required"}

def local_available(task_type:str)->bool:
    return task_type in LOCAL_PREPARERS
