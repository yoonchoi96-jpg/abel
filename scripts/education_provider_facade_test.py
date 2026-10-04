import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from education_provider_facade import execute_provider

def fake(model,payload):
    return {"choices":[{"message":{"content":"ok"}}]} if model=="deepseek" else {"output_text":"ok"}

def main():
    d=execute_provider("deepseek",{"text":"x"},fake)
    assert d["status"]=="dry_run"
    e=execute_provider("deepseek",{"text":"x"},fake,allow_api_call=True)
    assert e["status"]=="executed" and e["response"]["text"]=="ok"
    print("education_provider_facade_test: PASS")
if __name__=="__main__": main()
