from scripts.writing_practice_engine import prepare, finalize

RESOURCE={
 "id":"writing-demo","language":"zh-CN","level":"HSK6",
 "prompt":"请说明你最近一次学习中文的经历。",
 "source":"test","source_links":["drive://writing/demo"]
}

prepared=prepare(RESOURCE)
assert prepared["status"]=="ready_for_correction"

RESULT={
 "schema_version":"abel.multilingual.writing.v1",
 "engine":"Abel Multilingual Writing Correction Engine",
 "version":"1.0.0",
 "language":"zh-CN",
 "original":"我最近学习中文。",
 "overall":{"status":"correct","summary_ko":"정확합니다","severity":"none"},
 "versions":{
   "minimal_correction":"我最近学习中文。",
   "natural_version":"我最近在学习中文。",
   "advanced_version":"我最近一直在系统地学习中文。"
 },
 "issues":[],
 "vocabulary_usage":[],
 "assessment":{"target_level":"HSK6","score":80,"score_scale":"0-100","rationale_ko":"테스트"},
 "confidence":"high"
}
out=finalize(RESOURCE,"我最近学习中文。",RESULT)
assert out["resource_id"]=="writing-demo"
assert out["correction"]["original"]=="我最近学习中文。"

try:
    finalize(RESOURCE,"다른 문장",RESULT)
except ValueError:
    pass
else:
    raise AssertionError("original mismatch must fail")

print("writing_practice_engine_test: ok")
