#!/usr/bin/env python3
"""Task-level education gateway: local Abel engines first, then provider orchestration."""
from __future__ import annotations
from typing import Any, Callable
from education_router import route
from education_orchestrator import run
from education_task_adapters import prepare, require_source
from education_engine_bridge import local_available, prepare_local
from learning_pipeline import run as run_learning_pipeline
from learning_session import record_provider_event

SCHEMA="abel.education.gateway.v1"
PIPELINE_TASKS={"listening_practice","reading_practice"}

def execute_task(task_type:str,payload:dict[str,Any],provider_call:Callable,*,db_path="data/abel_education_router.db",learning_db_path="data/abel_learning.db",budget_units=None,estimated_units=1.0,allow_api_call=False,retry_limit=0):
    payload=prepare(task_type,payload)
    require_source(payload)

    if local_available(task_type):
        local_result=prepare_local(task_type,payload)
        execution={
            "status":"local",
            "source_of_truth":"Abel",
            "provider_called":False,
            "result":local_result,
        }

        if task_type in PIPELINE_TASKS and isinstance(local_result,dict) and local_result.get("results"):
            # Practice engines deliberately use resource-specific schemas.  The
            # gateway adds the canonical task kind required by the learning ledger.
            pipeline_result=dict(local_result)
            pipeline_result["kind"]=task_type.removesuffix("_practice")
            pipeline_result["unit_id"]=local_result.get("resource_id")
            pipeline=run_learning_pipeline([pipeline_result], learning_db_path)
            execution["learning_pipeline"]=pipeline

        return {
            "schema_version":SCHEMA,
            "task_type":task_type,
            "route":None,
            "execution":execution,
        }

    routed=route(task_type,payload)
    result=run(routed,payload,provider_call,db_path=db_path,budget_units=budget_units,estimated_units=estimated_units,allow_api_call=allow_api_call,retry_limit=retry_limit)
    if result.get("status")=="executed" and payload.get("language"):
        record_provider_event(payload["language"], task_type, result, model=result.get("model"), cache_key=routed.get("cache_key"), input_summary=str(payload.get("text") or payload.get("input") or payload.get("prompt") or "")[:500], db_path=learning_db_path)
        result["learning_event_recorded"]=True
    return {"schema_version":SCHEMA,"task_type":task_type,"route":routed,"execution":result}
