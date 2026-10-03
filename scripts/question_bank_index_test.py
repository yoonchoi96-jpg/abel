from scripts.question_bank_index import build
x=build([{"id":"x","title":"HSK6 Set 1","type":"listening","files":["a.mp3"],"related_items":["q"]}])
assert x["count"]==1 and x["items"][0]["status"]=="unknown"
print("question_bank_index_test: OK")
