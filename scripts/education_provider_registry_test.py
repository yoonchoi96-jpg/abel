import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from education_provider_registry import get,execution_plan

def main():
    assert get("deepseek")["credential_env"]=="DEEPSEEK_API_KEY"
    assert execution_plan(["deepseek","gpt"],cache_hit=True,budget_units=1,estimated_units=1)["status"]=="cache_hit"
    assert execution_plan(["deepseek"],cache_hit=False,budget_units=0,estimated_units=1)["status"]=="budget_blocked"
    p=execution_plan(["deepseek","gpt"],cache_hit=False,budget_units=2,estimated_units=1)
    assert p["status"]=="ready" and len(p["providers"])==2
    print("education_provider_registry_test: PASS")
if __name__=="__main__": main()
