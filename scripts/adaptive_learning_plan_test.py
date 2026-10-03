from scripts.adaptive_learning_plan import build_plan

def main():
    r=build_plan([
      {"id":"r2","kind":"reading","priority":10},
      {"id":"l1","kind":"listening","priority":9},
      {"id":"r1","kind":"reading","priority":8},
    ],{"reading":1,"listening":1})
    assert [x["id"] for x in r["items"]]==["r2","l1"]
    print("adaptive_learning_plan_test: PASS")

if __name__=="__main__": main()
