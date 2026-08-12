# D-Curb Guardian Streamlit Dashboard

## 실행

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

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

역할별 데모 로그인이 적용되어 있습니다. 데모용 비밀번호는 `modules/auth.py`에
평문으로 하드코딩되어 있으므로, 실제 운영 환경에서는 반드시 별도의 인증 수단으로
교체해야 합니다.
