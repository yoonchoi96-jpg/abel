from scripts.listening_practice_engine import score, validate_resource

RESOURCE={
 "id":"listen-demo","language":"zh-CN","level":"HSK6",
 "audio":"drive://audio/demo.mp3","transcript":"demo transcript",
 "source":"test","source_links":["drive://audio/demo.mp3"],
 "questions":[
  {"id":"q1","type":"choice"},
  {"id":"q2","type":"choice","error_type":"detail"}
 ],
 "answer_key":{"q1":"A","q2":"C"}
}

validate_resource(RESOURCE)
out=score(RESOURCE,{"q1":"A","q2":"B"})
assert out["total"]==2 and out["correct"]==1 and out["score"]==50
assert out["results"][1]["error_type"]=="detail"
assert out["audio"]=="drive://audio/demo.mp3"

try:
    bad=dict(RESOURCE)
    bad["answer_key"]={"q1":"A"}
    validate_resource(bad)
except ValueError:
    pass
else:
    raise AssertionError("mismatched answer key must fail")

print("listening_practice_engine_test: ok")
