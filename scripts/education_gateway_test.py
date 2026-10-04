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
        out=execute_task("chinese_writing_correction",{"text":"我喜欢学习中文","language":"zh-CN","target_level":"HSK6"},fake,db_path=t+"/db.sqlite",learning_db_path=t+"/learning.sqlite",allow_api_call=True)
        assert out["schema_version"]=="abel.education.gateway.v1"
        assert out["execution"]["status"]=="local"
        assert out["execution"]["provider_called"] is False
        assert out["execution"]["result"]["cache_key"]

        out=execute_task("adaptive_learning_plan",{"candidates":[{"id":"r1","kind":"reading","priority":2}]},fake,db_path=t+"/db.sqlite",learning_db_path=t+"/learning.sqlite")
        assert out["execution"]["status"]=="local"
        assert out["execution"]["result"]["count"]==1

        out=execute_task("hsks_exam_qa",{"questions":[{"number":1,"part":"listening","stem":"x","options":["A a","B b","C c","D d"],"answer":"A"}],"expected_total":1},fake,db_path=t+"/db.sqlite",learning_db_path=t+"/learning.sqlite")
        assert out["execution"]["status"]=="local"
        assert out["execution"]["result"]["engine"]=="Abel HSK Evaluation Engine"

        # Completed reading practice automatically enters the durable learning loop.
        resource={
            "id":"read-1","language":"zh-CN","level":"HSK6",
            "passage":"这是测试。","questions":[
                {"id":"q1","type":"choice","options":["A","B"],"answer":"A"},
                {"id":"q2","type":"choice","options":["A","B"],"answer":"B"},
            ],
            "answer_key":{"q1":"A","q2":"B"},
            "source":"test","source_links":[],
        }
        out=execute_task(
            "reading_practice",
            {"resource":resource,"answers":{"q1":"A","q2":"A"}},
            fake,
            db_path=t+"/db.sqlite",
            learning_db_path=t+"/learning.sqlite",
        )
        assert out["execution"]["status"]=="local"
        assert out["execution"]["provider_called"] is False
        pipeline=out["execution"]["learning_pipeline"]
        assert pipeline["sessions_recorded"]==1
        assert pipeline["error_review"]["count"]==1
        assert pipeline["adaptive_plan"]["count"]==1
        assert pipeline["adaptive_plan"]["items"][0]["id"]=="q2"

        out=execute_task("translation",{"text":"你好"},translation_fake,db_path=t+"/db.sqlite",learning_db_path=t+"/learning.sqlite",allow_api_call=True)
        assert out["execution"]["status"]=="executed"
        assert out["execution"]["result"]["response"]["text"]=="번역 완료"
    print("education_gateway_test: PASS")
if __name__=="__main__": main()
