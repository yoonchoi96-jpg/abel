import sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from education_orchestrator import run

def fake(model,payload):
    if model=="deepseek": return {"choices":[{"message":{"content":"ok"}}]}
    return {"output_text":"fallback"}

def main():
    route={"task_type":"translation","model_chain":["deepseek","gpt"],"cache_enabled":True,"cache_key":"orch-test"}
    with tempfile.TemporaryDirectory() as t:
        out=run(route,{"text":"x"},fake,db_path=t+"/db.sqlite",allow_api_call=True)
        assert out["status"]=="executed"
        assert out["result"]["result"]["response"]["text"]=="ok"
    print("education_orchestrator_test: PASS")
if __name__=="__main__": main()
