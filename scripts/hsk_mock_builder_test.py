#!/usr/bin/env python3
from scripts.hsk_mock_builder import build, load_profiles

PROFILES=load_profiles("data/hsk_exam_profiles.json")
UNITS=[
 {"id":"l6","kind":"listening","language":"zh-CN","level":"HSK6"},
 {"id":"r6","kind":"reading","language":"zh-CN","level":"HSK6"},
 {"id":"w6","kind":"writing","language":"zh-CN","level":"HSK6"}
]
out=build("HSK3.0-6",UNITS,PROFILES,mock_id="hsk6-mock-001")
assert out["exam_system"]=="HSK3.0"
assert [x["kind"] for x in out["sections"]]==["listening","reading","writing"]
assert [x["unit_id"] for x in out["sections"]]==["l6","r6","w6"]
assert out["sections"][0]["expected_items"]==50
assert out["sections"][2]["expected_items"]==1

try:
    build("HSK3.0-6",UNITS[:2],PROFILES,mock_id="bad")
except ValueError as e:
    assert "writing" in str(e)
else:
    raise AssertionError("missing source unit must fail")

UNITS79=[
 {"id":"l79","kind":"listening","language":"zh-CN","level":"HSK7-9"},
 {"id":"r79","kind":"reading","language":"zh-CN","level":"HSK7-9"},
 {"id":"w79","kind":"writing","language":"zh-CN","level":"HSK7-9"},
 {"id":"t79","kind":"translation","language":"zh-CN","level":"HSK7-9"},
 {"id":"s79","kind":"speaking","language":"zh-CN","level":"HSK7-9"}
]
out79=build("HSK3.0-7-9",UNITS79,PROFILES,mock_id="hsk79-mock-001")
assert [x["kind"] for x in out79["sections"]]==["listening","reading","writing","translation","speaking"]
assert [x["expected_items"] for x in out79["sections"]]==[40,47,2,4,5]

print("hsk_mock_builder_test: ok")
