# D-Curb Guardian Streamlit Dashboard

대전 도심물류 하역·주정차 위험관리 대시보드

[![배포](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://dcurb-guardian.streamlit.app/)

**🔗 대시보드 바로가기 — https://dcurb-guardian.streamlit.app/**

## 온라인에서 보기

위 링크로 접속한 뒤 역할을 선택하고 데모 비밀번호를 입력하면 바로 사용할 수 있습니다.
설치나 실행 과정이 필요 없습니다.

## 로컬 실행

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

React 대시보드는 `react_dist/` 빌드 산출물을 HTML에 인라인해 렌더링하므로
별도의 Node 서버가 없어도 동작합니다. 포트 3000에 Node 서버가 떠 있으면
그쪽을 우선 사용합니다.

## 화면 구조

- 1. 지자체 정책지원
- 2. 정책 시뮬레이터
- 3. 물류기업 운영지원
- 4. 배송기사 현장지원
- 5. 데이터·모델 설명

## 코드 구조

- `modules/`: 데이터 로딩, 후보지 추천, 정책 시뮬레이션, 날씨·트램·신뢰도·피드백 공통 로직
- `views/`: Streamlit 화면별 렌더링 코드
- `data/`: CSV/JSON 원천 데이터

## 로그인

역할별 데모 로그인이 적용되어 있으며, 역할에 따라 접근 가능한 화면이 달라집니다.

| 역할 | 비밀번호 | 접근 화면 |
|---|---|---|
| 지자체 | `dcurb2026` | 지자체 정책지원, 시뮬레이터, 날씨, 모델설명 |
| 물류기업 | `logi2026` | 물류기업 운영지원, 시뮬레이터, 날씨, 모델설명 |
| 배송기사 | `driver2026` | 배송기사 현장지원 |
| 분석가/관리자 | `admin2026` | 전체 |

위 비밀번호는 시연 목적의 데모 계정으로 `modules/auth.py`에 평문 하드코딩되어
있습니다. 실제 운영 환경에서는 반드시 별도의 인증 수단으로 교체해야 합니다.
