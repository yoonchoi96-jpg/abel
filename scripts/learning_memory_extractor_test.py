#!/usr/bin/env python3
from learning_memory_extractor import extract

events=[{
  "output":{"status":"executed","response":{"status":"success","text":"""{
    "issues":[{"issue_type":"grammar"},{"issue_type":"grammar"},{"issue_type":"word_choice"}],
    "vocabulary_usage":[
      {"word":"维护","status":"incorrect"},
      {"word":"维护","status":"incorrect"},
      {"word":"妥协","status":"awkward"}
    ]
  }"}}
}]
r=extract(events,"zh-CN")
assert r["schema_version"]=="abel.learning.memory.v1"
assert r["event_count"]==1
assert r["recurring_error_signals"][0]["type"]=="grammar"
assert r["recurring_error_signals"][0]["count"]==2
assert r["vocabulary_usage_signals"][0]["word"]=="维护"
assert r["vocabulary_usage_signals"][0]["status"]=="incorrect"
assert r["vocabulary_usage_signals"][0]["count"]==2
assert r["rules"]["no_invented_history"] is True
print("ok")
