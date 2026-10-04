#!/usr/bin/env python3
"""Abel Education Router execution ledger.

Provider adapters are intentionally injected by callers. This layer owns
deterministic cache lookup, retry sequencing, batch grouping, and budget gates.
It never stores provider secrets and never invents model output.
"""
from __future__ import annotations
import argparse, hashlib, json, sqlite3, time
from pathlib import Path
from typing import Any, Callable

SCHEMA="abel.education.executor.v1"

def connect(db_path="data/abel_education_router.db"):
    Path(db_path).parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(db_path)
    db.execute("""CREATE TABLE IF NOT EXISTS cache (
      cache_key TEXT PRIMARY KEY, task_type TEXT NOT NULL, model TEXT NOT NULL,
      status TEXT NOT NULL, response_json TEXT, created_at REAL NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS usage (
      id INTEGER PRIMARY KEY AUTOINCREMENT, task_type TEXT, model TEXT,
      cache_hit INTEGER NOT NULL, attempt INTEGER NOT NULL, units REAL,
      created_at REAL NOT NULL)""")
    db.commit()
    return db

def get_cached(db,key):
    row=db.execute("SELECT response_json FROM cache WHERE cache_key=? AND status='success'",(key,)).fetchone()
    return json.loads(row[0]) if row else None

def put_cached(db,key,task_type,model,response):
    db.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?,?,?,?)",
               (key,task_type,model,"success",json.dumps(response,ensure_ascii=False),time.time()))
    db.commit()

def execute(route:dict[str,Any], payload:dict[str,Any], providers:dict[str,Callable[[dict],dict]],
            *, db_path="data/abel_education_router.db", max_attempts=1,
            budget_units:float|None=None, estimated_units:float=1.0):
    if not isinstance(route,dict) or not route.get("cache_key"):
        raise ValueError("valid router output required")
    db=connect(db_path)
    key=route["cache_key"]
    if route.get("cache_enabled"):
        cached=get_cached(db,key)
        if cached is not None:
            db.execute("INSERT INTO usage(task_type,model,cache_hit,attempt,units,created_at) VALUES(?,?,?,?,?,?)",
                       (route["task_type"],"cache",1,0,0,time.time()))
            db.commit()
            return {"schema_version":SCHEMA,"status":"cache_hit","cache_key":key,"response":cached,"attempts":0}

    if budget_units is not None and estimated_units > budget_units:
        return {"schema_version":SCHEMA,"status":"budget_blocked","cache_key":key,"attempts":0}

    errors=[]
    models=route.get("model_chain",[])
    attempts=0
    for model in models:
        provider=providers.get(model)
        if provider is None:
            errors.append({"model":model,"error":"provider_not_configured"})
            continue
        for _ in range(max(1,max_attempts)):
            attempts+=1
            try:
                response=provider(payload)
                if not isinstance(response,dict):
                    raise ValueError("provider must return a JSON object")
                if route.get("cache_enabled"):
                    put_cached(db,key,route["task_type"],model,response)
                db.execute("INSERT INTO usage(task_type,model,cache_hit,attempt,units,created_at) VALUES(?,?,?,?,?,?)",
                           (route["task_type"],model,0,attempts,estimated_units,time.time()))
                db.commit()
                return {"schema_version":SCHEMA,"status":"executed","cache_key":key,"model":model,
                        "response":response,"attempts":attempts}
            except Exception as exc:
                errors.append({"model":model,"error":str(exc)})
    return {"schema_version":SCHEMA,"status":"failed","cache_key":key,"attempts":attempts,"errors":errors}

def batch_groups(requests:list[dict[str,Any]])->list[list[dict[str,Any]]]:
    groups={}
    for req in requests:
        r=req.get("route",{})
        key=(r.get("primary_model"),r.get("task_type"),bool(r.get("batchable")))
        groups.setdefault(key,[]).append(req)
    return [groups[k] for k in sorted(groups,key=lambda x:str(x))]

def fingerprint_budget(budget:dict[str,float])->str:
    return hashlib.sha256(json.dumps(budget,sort_keys=True,separators=(",",":")).encode()).hexdigest()
