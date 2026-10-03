from scripts.reading_practice_engine import score, validate_resource

RESOURCE={
 "id":"reading-demo","language":"zh-CN","level":"HSK6",
 "passage":"这是测试文章。","source":"test",
 "source_links":["drive://reading/demo"],
 "questions":[
  {"id":"q1","type":"choice"},
  {"id":"q2","type":"cloze","error_type":"vocabulary"}
 ],
 "answer_key":{"q1":"A","q2":"B"}
}

validate_resource(RESOURCE)
out=score(RESOURCE,{"q1":"A","q2":"C"})
assert out["total"]==2 and out["correct"]==1 and out["score"]==50
assert out["results"][1]["error_type"]=="vocabulary"
assert out["passage"]=="这是测试文章。"

print("reading_practice_engine_test: ok")
