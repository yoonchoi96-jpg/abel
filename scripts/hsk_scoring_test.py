import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hsk_scoring import score_profile, load_profiles

def main():
    profiles=load_profiles()
    result={"language":"zh-CN","sections":[
      {"kind":"listening","total":50,"correct":45},
      {"kind":"reading","total":50,"correct":40},
      {"kind":"writing","total":1,"correct":1}
    ]}
    out=score_profile("HSK3.0-6",result,profiles)
    assert out["total_score"]==270.0
    assert out["official_equivalence"] is False

    r79={"language":"zh-CN","sections":[
      {"kind":"listening","total":40,"correct":30},
      {"kind":"reading","total":47,"correct":35},
      {"kind":"writing","total":2,"correct":1},
      {"kind":"translation","total":4,"correct":2},
      {"kind":"speaking","total":5,"correct":4}
    ]}
    out79=score_profile("HSK3.0-7-9",r79,profiles)
    assert out79["calibration_status"]=="not_calibrated"
    assert out79["total_score"] is None
    print("hsk_scoring_test: PASS")

if __name__=="__main__":
    main()
