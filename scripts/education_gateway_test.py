import sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from education_gateway import execute_task

def fake(model,payload):
    raise AssertionError("provider must not be called for local Abel tasks")

def translation_fake(model,payload):
    return {"choices":[{"message":{"content":"번역 완료"}}]}

def main():
    with tempfile.TemporaryDirectory() as t:
        out=execute_task("chinese_writing_correction",{"text":"我喜欢学习中文","language":"zh-CN","target_level":"HSK6"},fake,db_path=t+"/db.sqlite",allow_api_call=True)
        assert out["schema_version"]=="abel.education.gateway.v1"
        assert out["execution"]["status"]=="local"
        assert out["execution"]["provider_called"] is False
        assert out["execution"]["result"]["cache_key"]

        out=execute_task("adaptive_learning_plan",{"candidates":[{"id":"r1","kind":"reading","priority":2}]},fake,db_path=t+"/db.sqlite")
        assert out["execution"]["status"]=="local"
        assert out["execution"]["result"]["count"]==1

        out=execute_task("hsks_exam_qa",{"questions":[{"number":1,"part":"listening","stem":"x","options":["A a","B b","C c","D d"],"answer":"A"}],"expected_total":1},fake,db_path=t+"/db.sqlite")
        assert out["execution"]["status"]=="local"
        assert out["execution"]["result"]["engine"]=="Abel HSK Evaluation Engine"

        out=execute_task("translation",{"text":"你好"},translation_fake,db_path=t+"/db.sqlite",allow_api_call=True)
        assert out["execution"]["status"]=="executed"
        assert out["execution"]["result"]["response"]["text"]=="번역 완료"
    print("education_gateway_test: PASS")
if __name__=="__main__": main()
