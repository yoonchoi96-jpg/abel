#!/usr/bin/env python3
"""End-to-end provider-aware execution orchestration for Abel."""
from __future__ import annotations
from typing import Any, Callable
from education_executor import execute
from education_provider_facade import execute_provider
from education_provider_registry import execution_plan

SCHEMA="abel.education.orchestrator.v1"

def run(route:dict[str,Any], payload:dict[str,Any], provider_call:Callable[[str,dict],dict], *, db_path="data/abel_education_router.db", budget_units=None, estimated_units=1.0, allow_api_call=False, retry_limit=0):
    if not route.get("cache_key"): raise ValueError("valid router output required")
    plan=execution_plan(route.get("model_chain",[]),cache_hit=False,budget_units=budget_units,estimated_units=estimated_units)
    if plan["status"]!="ready":
        return {"schema_version":SCHEMA,"status":plan["status"],"plan":plan}
    if route.get("cache_enabled"):
        cached=execute(route,payload,{},db_path=db_path,budget_units=budget_units,estimated_units=estimated_units)
        if cached["status"]=="cache_hit": return {"schema_version":SCHEMA,"status":"cache_hit","result":cached,"plan":plan}
    models=route.get("model_chain",[])
    errors=[]
    for index,model in enumerate(models):
        result=execute_provider(model,payload,provider_call,allow_api_call=allow_api_call,retry_limit=retry_limit,fallback_available=index<len(models)-1)
        if result["status"] in ("executed","dry_run"):
            return {"schema_version":SCHEMA,"status":result["status"],"model":model,"result":result,"plan":plan}
        errors.append(result)
    return {"schema_version":SCHEMA,"status":"failed","errors":errors,"plan":plan}
