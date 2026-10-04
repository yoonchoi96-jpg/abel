import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from education_execution_policy import classify_error,next_action

def main():
    assert classify_error({"http_status":429})=="retryable"
    assert classify_error({"http_status":401})=="non_retryable"
    assert next_action({"http_status":503},retry_count=0,max_retries=2,fallback_available=True)=="retry"
    assert next_action({"http_status":401},retry_count=0,max_retries=2,fallback_available=True)=="fallback"
    assert next_action({"x":"bad"},retry_count=2,max_retries=2,fallback_available=False)=="fail"
    print("education_execution_policy_test: PASS")
if __name__=="__main__": main()
