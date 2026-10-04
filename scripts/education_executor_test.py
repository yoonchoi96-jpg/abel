import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from education_executor import execute, batch_groups

def provider(payload):
    return {'ok': True, 'echo': payload}

def test_cache():
    route={'task_type':'translation','model_chain':['deepseek','gpt'],'cache_enabled':True,'cache_key':'test-cache-key'}
    db='data/test-router.db'
    first=execute(route,{'x':1},{'deepseek':provider},db_path=db)
    second=execute(route,{'x':1},{'deepseek':provider},db_path=db)
    assert first['status']=='executed'
    assert second['status']=='cache_hit'

def test_budget():
    route={'task_type':'translation','model_chain':['deepseek'],'cache_enabled':False,'cache_key':'budget-key'}
    out=execute(route,{'x':1},{'deepseek':provider},db_path='data/test-router-budget.db',budget_units=0,estimated_units=1)
    assert out['status']=='budget_blocked'

def test_batch():
    groups=batch_groups([{'route':{'primary_model':'gemini','task_type':'x','batchable':True}},{'route':{'primary_model':'gemini','task_type':'x','batchable':True}},{'route':{'primary_model':'gpt','task_type':'x','batchable':True}}])
    assert sorted(len(g) for g in groups)==[1,2]
