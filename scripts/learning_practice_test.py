from scripts.learning_practice import score

def main():
    unit={"id":"demo","kind":"reading","language":"zh-CN","level":"HSK6",
          "questions":[{"id":"q1","answer":"A"},{"id":"q2","answer":"C"}]}
    result=score(unit,{"q1":"A","q2":"B"})
    assert result["correct"]==1 and result["total"]==2 and result["score"]==50.0
    assert result["results"][1]["expected"]=="C"
    print("learning_practice_test: PASS")

if __name__=="__main__": main()
