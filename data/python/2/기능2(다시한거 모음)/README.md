# D-Curb Guardian Feature 2

## 포함 파일

| 파일 | 용도 |
| --- | --- |
| `01_create_risk_type_master.py` | 82개 행정동 위험유형 분류 실행 |
| `02_create_html_demo.py` | 실제 CSV를 포함한 오프라인 HTML 생성 |
| `03_create_feature2_workbook.py` | 무채색 Excel 결과 통합본 생성 |
| `dcurb_config.py` | 팀 공통 경로 설정 |
| `risk_type_master.csv` | 행정동별 최종 분류 결과 |
| `risk_type_rules.csv` | 7개 유형 판정 규칙 |
| `D_Curb_Guardian_Feature2_Streamlit.py` | 기능 2 시연 화면 |
| `requirements.txt` | Streamlit 실행 패키지 |
| `Feature2_Risk_Type_Classification.md` | 기능 설명·분석 과정·결과 |
| `Feature2_Risk_Type_Demo.html` | 설치 없이 열 수 있는 시연 화면 |
| `Feature2_Risk_Type_Results.xlsx` | 파란색 없는 무채색 결과 통합본 |
| `regional_context_template.csv` | 지역특성 접두어 연결용 선택 양식 |

## Colab에서 분류 결과 만들기

Google Drive에서 다음 폴더 구조를 사용한다.

```text
/content/drive/MyDrive/modeling/
└── logistic/
    └── final/
        ├── final_modelling.csv
        ├── regional_context.csv          # 선택
        └── feature2/                     # 자동 생성
            ├── risk_type_master.csv
            └── risk_type_rules.csv
```

Colab 코드 셀에서 실행한다.

```python
%cd /content/drive/MyDrive/modeling/logistic/final/feature2_code
!python 01_create_risk_type_master.py
```

다른 위치에서 실행할 때는 프로젝트 루트를 환경변수로 지정할 수 있다.

```python
import os
os.environ["DCURB_PROJECT_ROOT"] = "/content/drive/MyDrive/modeling"
```

## Streamlit 실행

```bash
pip install -r requirements.txt
streamlit run D_Curb_Guardian_Feature2_Streamlit.py
```

필수 파일 5개를 같은 폴더에 두면 바로 실행된다.

```text
D_Curb_Guardian_Feature2_Streamlit.py
dcurb_config.py
risk_type_master.csv
risk_type_rules.csv
requirements.txt
```

조원 통합 시간대 화면까지 함께 실행하려면 다음 파일을 `input_data/` 폴더에 둔다.

```text
input_data/
├── final_modelling.csv
├── logistics_view_timeband_v3.csv
├── driver_view_timeband_v3.csv
└── driver_facing_policy_text.csv
```

`final_modelling.csv`만 위험유형 분류에 사용하며, 나머지 3개 CSV는 물류기업·배송기사 화면에 행정동코드로 연결한다.

GeoJSON 지도는 `daejeon_admin_dong.geojson`을 같은 폴더에 추가하거나 화면에서 업로드하면 활성화된다.

## HTML과 Excel 다시 만들기

```bash
python 02_create_html_demo.py
python 03_create_feature2_workbook.py
```

`Feature2_Risk_Type_Demo.html`은 브라우저에서 바로 열 수 있다. Excel 통합본은 기본 표 스타일을 사용하지 않고 회색·흰색만 지정했다.

## AI Studio 사용 여부

이 기능은 CSV 처리·필터·그래프·지도·정책 연결이 중심이므로 Streamlit에 넣는 것이 적합하다. Google AI Studio는 생성형 AI 프롬프트와 모델 응답 실험용이므로 이 MVP의 실행 화면으로 사용하지 않는다.

## 지역특성 태그 추가

`regional_context_template.csv`의 82개 행정동코드에 실제 근거값을 입력한 뒤 파일명을 `regional_context.csv`로 바꿔 `logistic/final/` 폴더에 둔다.

- 점수는 0~100 백분위 사용
- 70점 이상인 실제 특성만 접두어 후보가 됨
- 세 특성이 모두 기준을 충족하면 가장 높은 특성 하나를 사용
- 값이 없으면 공동주택·상권·역세권 명칭을 붙이지 않음
