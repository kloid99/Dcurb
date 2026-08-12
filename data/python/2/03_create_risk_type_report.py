"""
risk_type_master.csv와 risk_type_rules.csv를 이용해 분석과정보고서 MD를 생성합니다.

권장 실행 환경: Google Colab
입력 파일: risk_type_master.csv, risk_type_rules.csv
출력 파일: 서식3_기능2_행정동위험유형자동분류_초안.md
"""

from pathlib import Path

import pandas as pd


BASE_DIR = Path("/content/drive/MyDrive/modeling")
OUTPUT_DIR = BASE_DIR / "risk_type_output"
MASTER_CSV = OUTPUT_DIR / "risk_type_master.csv"
RULES_CSV = OUTPUT_DIR / "risk_type_rules.csv"
OUTPUT_MD = OUTPUT_DIR / "서식3_기능2_행정동위험유형자동분류_초안.md"


TYPE_ORDER = [
    "공동주택 배송집중형",
    "상권·교통 혼잡형",
    "역세권 보행충돌형",
    "단속반복형",
    "안전취약형",
    "하역공간 부족형",
]


def mount_google_drive() -> None:
    try:
        from google.colab import drive

        drive.mount("/content/drive", force_remount=False)
    except ImportError:
        pass


def read_csv_auto(path: Path) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"CSV 인코딩을 확인할 수 없습니다: {path}")


def create_distribution_table(master: pd.DataFrame) -> str:
    counts = master["주위험유형"].value_counts().reindex(TYPE_ORDER, fill_value=0)
    rows = ["| 위험유형 | 행정동 수 |", "| --- | ---: |"]
    rows.extend(f"| {risk_type} | {int(counts[risk_type])} |" for risk_type in TYPE_ORDER)
    return "\n".join(rows)


def create_representative_table(master: pd.DataFrame) -> str:
    rows = [
        "| 위험유형 | 대표 행정동 | DLFI | 주요 분류 근거 |",
        "| --- | --- | ---: | --- |",
    ]
    for risk_type in TYPE_ORDER:
        subset = master[master["주위험유형"] == risk_type].sort_values(
            "DLFI", ascending=False
        )
        if subset.empty:
            rows.append(f"| {risk_type} | 해당 없음 | - | - |")
            continue
        row = subset.iloc[0]
        location = f"{row['시군구']} {row['행정동']}"
        basis = (
            f"{row['주요근거지표']} {float(row['주요원점수']):.2f}점"
            f"·백분위 {float(row['주요위험백분위']):.1f}"
        )
        rows.append(f"| {risk_type} | {location} | {float(row['DLFI']):.2f} | {basis} |")
    return "\n".join(rows)


def create_rule_table(rules: pd.DataFrame) -> str:
    rows = [
        "| 위험유형 | 핵심 판단지표 | 기본 관리 방향 |",
        "| --- | --- | --- |",
    ]
    for _, row in rules.iterrows():
        rows.append(
            f"| {row['위험유형']} | {row['판단지표']} | {row['정책활용방향']} |"
        )
    return "\n".join(rows)


def create_report(master_csv: Path, rules_csv: Path, output_md: Path) -> str:
    master = read_csv_auto(master_csv)
    rules = read_csv_auto(rules_csv)

    distribution_table = create_distribution_table(master)
    representative_table = create_representative_table(master)
    rule_table = create_rule_table(rules)
    district_count = len(master)

    report = f"""# 행정동 위험유형 자동 분류

> 담당: 엄세용 · 산출 파일: `risk_type_rules.csv`, `risk_type_master.csv`

---

## 1. 기능 개요

본 기능은 행정동별 DLFI 총점만 보여주는 방식에서 벗어나, **어떤 위험요인이 해당 지역의 생활물류 마찰을 주도하는지 자동으로 분류**합니다.

같은 고위험 지역이라도 배송수요, 보행충돌, 반복단속, 안전취약, 하역공간 부족 등 원인이 다르기 때문에 동일한 정책을 적용하면 효과가 낮을 수 있습니다. 따라서 {district_count}개 행정동의 6개 세부지표를 동일한 백분위 기준으로 비교해 주위험유형과 보조위험유형을 산출하고, 유형에 맞는 관리 방향을 함께 제공합니다.

```
행정동별 6개 DLFI 세부지표
        ↓
위험방향 통일 및 행정동 백분위 변환
        ↓
주위험유형·보조위험유형 자동 지정
        ↓
기존 K-Means 군집 결과와 교차 확인
        ↓
유형별 정책 관리 방향 제공
```

---

## 2. 산출 방법

### 2-1. 입력 데이터

기준 입력 파일은 `final_modelling.csv`이며 대전시 {district_count}개 행정동을 대상으로 다음 지표를 사용했습니다.

| 지표 | 원본 컬럼 | 위험방향 |
| --- | --- | --- |
| 배송수요 | 배송수요점수_최종 | 높을수록 위험 |
| 교통방해 | 교통방해점수 | 높을수록 위험 |
| 보행충돌 | 보행충돌점수_최종 | 높을수록 위험 |
| 단속반복 | 단속반복점수 | 높을수록 위험 |
| 안전취약 | 안전취약점수 | 높을수록 위험 |
| 하역부족 | 하역여유점수 | 낮을수록 위험 |

### 2-2. 백분위 변환

원점수는 지표마다 분포와 범위가 다르므로 그대로 비교하지 않았습니다. 각 지표를 {district_count}개 행정동 내 위험 백분위로 변환했습니다.

```
일반 위험지표 = 해당 값보다 낮은 행정동의 비율
하역부족지표 = 해당 값보다 하역여유가 높은 행정동의 비율
```

특히 하역여유점수는 값의 범위가 다른 지표보다 작으므로 단순히 `100-원점수`를 적용하면 하역부족형으로 분류가 쏠릴 수 있습니다. 이를 방지하기 위해 **순위 기반 백분위**를 사용했습니다.

### 2-3. 위험유형 지정

6개 위험 백분위 중 가장 높은 지표를 주위험유형, 두 번째 지표를 보조위험유형으로 지정했습니다.

{rule_table}

### 2-4. 분류명확도

분류명확도는 주위험 백분위와 보조위험 백분위의 차이로 계산했습니다.

```
분류명확도 = 50 + (주위험백분위 - 보조위험백분위) × 0.5
상한값 = 95
```

이 값은 통계적 예측확률이 아니라 **두 위험요인 중 어느 요인이 상대적으로 더 뚜렷한지를 보여주는 설명용 지표**입니다.

### 2-5. 기존 군집과의 관계

기존 K-Means 군집과 군집유형은 제거하지 않고 보조 설명으로 유지했습니다. K-Means는 비슷한 지표 구조를 가진 지역군을 찾는 역할을 하고, 본 기능은 각 행정동에 정책 대응이 가능한 세부 위험 라벨을 부여하는 역할을 합니다.

---

## 3. 산출 결과

### 3-1. 위험유형 분포

{distribution_table}

### 3-2. 유형별 대표 고위험 지역

{representative_table}

각 행정동에는 주위험유형뿐 아니라 보조위험유형과 6개 지표별 위험 백분위를 함께 저장해, 대시보드에서 분류 근거를 확인할 수 있도록 했습니다.

---

## 4. 화면 적용 방법

### 4-1. 행정동 상세 카드

```
행정동: 선택 행정동
DLFI: 행정동별 최종 점수
주위험유형: 자동 분류 결과
보조위험유형: 자동 분류 결과
주요 위험근거: 원점수 + 행정동 백분위
권장 관리방향: 유형별 정책 문구
```

### 4-2. 위험지도 필터

- 전체 행정동
- 공동주택 배송집중형
- 상권·교통 혼잡형
- 역세권 보행충돌형
- 단속반복형
- 안전취약형
- 하역공간 부족형

### 4-3. 정책 기능 연결

```
위험유형 자동 분류
        ↓
유형별 정책 패키지 후보 제시
        ↓
하역공간 후보지·운영시간 추천
        ↓
정책 What-if 시뮬레이터에서 효과 비교
```

---

## 5. 차별성

| 기존 방식 | 본 기능 |
| --- | --- |
| DLFI 총점과 순위만 제공 | 위험을 발생시킨 주요 원인을 함께 제공 |
| 군집번호 중심의 분석 결과 | 행정 담당자가 이해할 수 있는 정책형 유형명 제공 |
| 동일 고위험 지역에 유사한 대응 | 배송수요·보행·단속·안전·하역부족 원인별 대응 |
| 원점수 범위가 다른 지표를 직접 비교 | 행정동 백분위로 변환해 동일 기준에서 비교 |
| 결과 설명이 별도 문서에 존재 | 대시보드 상세 카드에서 근거와 관리방향을 즉시 확인 |

---

## 6. 한계사항 및 활용 주의

- 위험유형은 인과관계를 확정하는 결과가 아니라, 현재 확보한 공공데이터에서 상대적으로 두드러진 위험요인을 설명하는 분류입니다.
- 백분위는 대전 {district_count}개 행정동 내부의 상대평가이므로 다른 도시와 직접 비교할 수 없습니다.
- 교통방해점수의 대체값과 하역여유점수의 변별력은 분류 결과 해석 시 함께 표시해야 합니다.
- 주위험과 보조위험 백분위 차이가 작은 지역은 단일 유형보다 복합위험 지역으로 해석해야 합니다.
- 입력 데이터에서 이상치로 분리된 지역은 별도 품질 플래그와 함께 확인해야 합니다.
- 본 기능은 기존 DLFI를 수정하지 않으며, DLFI 결과를 해석하고 정책 방향을 구체화하는 설명 기능입니다.

---

## 7. 산출 파일 구조

### `risk_type_master.csv`

행정동별 주위험유형, 보조위험유형, 분류근거, 6개 위험백분위, 권장 관리방향을 저장합니다.

### `risk_type_rules.csv`

6개 위험유형별 기준지표, 위험방향, 산출기준, 정책 활용방향과 차별성을 정의합니다.
"""

    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(report, encoding="utf-8")
    print(f"[완료] {output_md}")
    return report


if __name__ == "__main__":
    mount_google_drive()
    create_report(MASTER_CSV, RULES_CSV, OUTPUT_MD)
