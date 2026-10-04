#!/usr/bin/env python3
"""Task-level education gateway: Router + orchestration with explicit policy."""
from __future__ import annotations
from typing import Any, Callable
from education_router import route
from education_orchestrator import run
from education_task_adapters import prepare, require_source

SCHEMA="abel.education.gateway.v1"

def execute_task(task_type:str,payload:dict[str,Any],provider_call:Callable,*,db_path="data/abel_education_router.db",budget_units=None,estimated_units=1.0,allow_api_call=False,retry_limit=0):
    payload=prepare(task_type,payload)
    require_source(payload)
    routed=route(task_type,payload)
    result=run(routed,payload,provider_call,db_path=db_path,budget_units=budget_units,estimated_units=estimated_units,allow_api_call=allow_api_call,retry_limit=retry_limit)
    return {"schema_version":SCHEMA,"task_type":task_type,"route":routed,"execution":result}
