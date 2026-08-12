# D-Curb Guardian Streamlit 실행 방법

## 1. 필요한 파일

다음 네 파일을 같은 폴더에 둡니다.

- `D_Curb_Guardian_Streamlit.py`
- `requirements.txt`
- `risk_type_master.csv`
- `risk_type_rules.csv`

## 2. 로컬 실행

```bash
pip install -r requirements.txt
streamlit run D_Curb_Guardian_Streamlit.py
```

## 3. Streamlit Community Cloud 배포

1. GitHub 저장소에 네 파일을 업로드합니다.
2. Streamlit Community Cloud에서 저장소를 연결합니다.
3. Main file path를 `D_Curb_Guardian_Streamlit.py`로 지정합니다.
4. Deploy를 실행합니다.

## 4. 구현 기능

- 시군구·주위험유형 필터
- 행정동 선택
- DLFI·순위·분류명확도 카드
- 6개 위험요인 백분위 그래프
- 주위험·보조위험 분류 근거
- 위험유형별 권장 관리방향
- 전체 위험유형 분포
- 행정동 우선순위 표와 CSV 다운로드
- 두 행정동 비교
- 분류기준 확인
- 행정동 경계 GeoJSON 기반 DLFI 위험지도
- 위험유형별 정책 패키지 추천
- 하역공간 후보지 데이터 연결 화면
- 정책 What-if 시뮬레이터
- 데이터 신뢰도·품질관리 레이어

## 5. 지도와 팀원 파일 연결

- 지도: `daejeon_admin_dong.geojson`
- 하역공간 후보지: `loading_zone_candidates.csv`
- 데이터 신뢰도: `reliability_master.csv`
- 데이터 출처: `data_source_registry.csv`

지도와 하역공간 후보지 파일이 아직 없으면 앱 화면에서 연결 규격을
안내하고, 파일을 추가하면 자동으로 해당 기능이 활성화됩니다.

AI Studio에는 입력하지 않습니다. AI Studio는 Gemini 모델과 프롬프트를
시험하는 도구이며, 본 서비스는 Streamlit에서 실행합니다.
