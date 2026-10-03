from scripts.error_review_engine import build_review

def main():
    r=build_review([
      {"question_id":"q2","correct":False,"wrong_count":3,"attempts":1,"error_type":"vocab","language":"zh-CN","level":"HSK6"},
      {"question_id":"q1","correct":True},
    ])
    assert r["count"]==1 and r["items"][0]["question_id"]=="q2"
    print("error_review_engine_test: PASS")

if __name__=="__main__": main()
