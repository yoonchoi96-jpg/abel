# Abel — 네이버 중국어 단어장 내부 요청 검증 (로컬 전용)

## 목적 및 현재 상태

이 도구는 개인 네이버 단어장 화면에서 발생하는 XHR/fetch 응답의 메타데이터만 확인한다.
공식 네이버 API가 아니고, 개인 단어장 내부 API 엔드포인트는 아직 검증되지 않았다.
이 단계에서는 API를 직접 호출하거나 단어장을 자동 동기화하지 않는다.

운영 Abel의 데이터 경계인 data/naver_wordbook.json 및 현재 운영 자동화는 변경하지 않는다.
네이버 로그인 및 관찰은 사용자가 소유한 Mac 로컬 브라우저에서만 수행한다.

## Mac에서 시험하기

    git clone https://github.com/yoonchoi96-jpg/abel.git
    cd abel
    git fetch origin feat/naver-readonly-network-probe-20261023
    git switch --track origin/feat/naver-readonly-network-probe-20261023

    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install playwright
    python -m playwright install chromium
    python scripts/naver_network_probe.py --duration 90

이미 Abel 저장소가 있으면 git clone을 생략하고 해당 디렉터리에서 git fetch/git switch만 수행한다.
동일한 로그인 프로필을 사용하는 다른 Abel 스크래퍼가 실행 중이면 먼저 종료한다.

실행 시 새 Chromium 창이 열리면 직접 네이버에 로그인한다.
로그인 후 터미널에서 Enter를 누르고 서로 다른 중국어 단어장 2~3개와 다음 페이지를 클릭한다.
단어를 실제로 추가하거나 삭제할 필요는 없다.

기본 결과:

    ~/Documents/Abel_Naver_Wordbook/naver_api_probe.json

### 무엇을 저장하는가?

- 호스트 및 민감한 식별자를 제거한 경로
- GET/POST 등의 요청 메서드, HTTP 상태 코드, 호출 횟수
- URL의 쿼리 키 이름만 (예: page, wbId; 값은 저장하지 않음)
- JSON 구조의 필드 이름 및 값의 자료형만
- 단어장 관련 요청 후보 점수

절대 저장하지 않는 것: 로그인 ID/비밀번호, 쿠키, 인증 헤더, 전체 HTTP 응답 본문,
실제 단어, 뜻, 폴더명, 폴더 ID, 쿼리 값, HAR 파일. 브라우저 로그인 세션은 Mac의
~/.naver_wordbook/browser_profile 안에만 유지한다. 해당 폴더를 GitHub/Drive에 업로드하지 않는다.

이 도구는 페이지를 사용자가 클릭하는 동안 발생하는 요청을 관찰할 뿐이며,
별도로 숨겨진 API를 호출하지 않는다. 불명확한 엔드포인트에 대한 요청 재현·변조,
자동 재로그인, CAPTCHA 우회는 하지 않는다.

## 실제 연동 전 검증 단계

1. 메타데이터의 후보 중 폴더 목록 응답과 카드 목록 응답을 식별한다.
2. 엔드포인트가 사용자 자신의 단어 목록에 대한 읽기 요청인지, 해당 사용 방식이 허용되는지 검토한다.
3. 성공 응답과 폴더/페이지 단위 누락·중복 문제를 화면에서 본 실제 수량과 대조한다.
4. 허용되는 읽기 방식이 확인되면 변경분 스냅샷을 만든 뒤 기존 Abel의 데이터 입력 경계로 전달한다.
5. 실패, 인증 만료, 누락 페이지, 403/429가 발생하면 삭제를 반영하지 않는다.
6. 적절한 직접 호출 방식이 없다면 기존의 사용자 로컬 Playwright DOM 수집 방식만 사용한다.

## 주의

네이버는 개인 단어장용 공개 API를 제공하는 것으로 확인되지 않았다.
이 진단 도구의 존재는 내부 API가 실제로 사용 가능하거나 네이버가 자동 호출을 허가했다는 뜻이 아니다.
서비스 약관·접근 정책을 준수하고, 과도한 빈도의 호출이나 차단 우회는 하지 않는다.

테스트는 로컬에서 다음 명령으로 네트워크 없이 실행할 수 있다.

    python -m unittest discover -s tests -p test_naver_network_probe.py -v
