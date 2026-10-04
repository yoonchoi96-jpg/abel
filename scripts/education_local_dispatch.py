#!/usr/bin/env python3
"""Deterministic local task dispatch over Abel's existing engines."""
from __future__ import annotations
from typing import Any
from education_engine_bridge import prepare_local

def dispatch(task_type:str,payload:dict[str,Any])->dict[str,Any]:
    result=prepare_local(task_type,payload)
    return {"schema_version":"abel.education.local-dispatch.v1","task_type":task_type,"result":result,"local":result.get("execution")!="provider_required"}
