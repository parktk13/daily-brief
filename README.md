# DAILY BRIEF — RSS 자동 수집 시제품

이 버전은 정적 웹사이트에 RSS 뉴스 제목·요약·출처 링크를 자동 반영하는 시작용 프로젝트입니다.

## 포함 기능
- 반응형 웹 화면
- 기술 / 미국 증시 / 한국 증시 분류
- Google News RSS 검색 결과 수집
- 매일 한국시간 오전 8시 20분 자동 수집 (GitHub Actions)
- 수동 실행 가능 (`Actions` → `Update Daily Brief RSS` → `Run workflow`)
- 날짜별 JSON 보관 및 최신 뉴스 화면 표시

## GitHub Pages 무료 배포
1. GitHub에서 새 Public 저장소를 만듭니다. 예: `daily-brief`
2. 이 폴더 안의 파일과 `.github` 폴더를 저장소 최상위에 올립니다.
3. 저장소 `Settings → Pages`에서 `Deploy from a branch`, `main`, `/(root)`를 선택하고 저장합니다.
4. `Settings → Actions → General`에서 workflow가 저장소에 쓰기 권한을 갖도록 허용합니다. (Workflow permissions: Read and write permissions)
5. `Actions` 탭에서 `Update Daily Brief RSS`를 수동 실행해 첫 데이터를 생성합니다.
6. `https://깃허브아이디.github.io/daily-brief/` 주소로 확인합니다.

## 현재 단계의 한계
- RSS 제목·발췌문 수집이지, AI가 기사 전문을 읽고 분석한 결과가 아닙니다.
- Google News RSS 검색 결과는 누락·중복·언어별 편차가 있을 수 있습니다.
- 이 버전은 주가지수·종목별 가격이나 상승/하락률을 가져오지 않습니다. 확인되지 않은 시세를 표시하지 않도록 시장 브리핑은 안내 문구로 남겨 두었습니다.
- 실시간/지연 시세 API와 AI 요약 API는 제공 조건 및 비용을 별도로 확인해야 합니다.
- 원문 기사를 복제하지 않고 제목·짧은 발췌와 원문 링크만 표시합니다. 각 출처의 이용약관과 RSS 사용 조건을 확인하세요.

## 로컬 테스트
Python 3.10 이상에서:
```bash
python fetch_news.py
```
그 다음 `index.html`을 로컬 서버로 열어야 JSON fetch가 동작합니다. 예:
```bash
python -m http.server 8000
```
브라우저에서 `http://localhost:8000`을 엽니다.
