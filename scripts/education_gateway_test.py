import sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from education_gateway import execute_task

def fake(model,payload):
    return {"choices":[{"message":{"content":"번역 완료"}}]}

def main():
    with tempfile.TemporaryDirectory() as t:
        out=execute_task("translation",{"text":"你好"},fake,db_path=t+"/db.sqlite",allow_api_call=True)
        assert out["schema_version"]=="abel.education.gateway.v1"
        assert out["execution"]["status"]=="executed"
        assert out["execution"]["result"]["response"]["text"]=="번역 완료"
    print("education_gateway_test: PASS")
if __name__=="__main__": main()
