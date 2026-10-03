#!/usr/bin/env python3
from scripts.mock_test_engine import aggregate, validate_mock

UNITS=[
 {"id":"l1","kind":"listening","language":"zh-CN","level":"HSK6","questions":[{"id":"q1","answer":"A"}]},
 {"id":"r1","kind":"reading","language":"zh-CN","level":"HSK6","questions":[{"id":"q2","answer":"B"}]},
 {"id":"w1","kind":"writing","language":"zh-CN","level":"HSK6","questions":[{"id":"q3","answer":"C"}]},
]
MOCK={"id":"m1","language":"zh-CN","level":"HSK6","exam_system":"HSK3.0","source":"test",
      "source_links":["source://m1"],
      "sections":[
       {"kind":"listening","unit_id":"l1"},
       {"kind":"reading","unit_id":"r1"},
       {"kind":"writing","unit_id":"w1"}]}

RESULTS=[
 {"unit_id":"l1","kind":"listening","total":10,"correct":8,"score":80},
 {"unit_id":"r1","kind":"reading","total":10,"correct":7,"score":70},
]

validate_mock(MOCK,UNITS)
out=aggregate(MOCK,UNITS,RESULTS)
assert out["total"]==20
assert out["correct"]==15
assert out["score"]==75
assert out["source_links"]==["source://m1"]
assert out["sections"][2]["status"]=="not_attempted"

try:
    bad=dict(MOCK)
    bad["sections"]=[{"kind":"listening","unit_id":"missing"}]
    validate_mock(bad,UNITS)
except ValueError:
    pass
else:
    raise AssertionError("unknown unit must fail")

print("mock_test_engine_test: ok")
