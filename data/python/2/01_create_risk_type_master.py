"""
행정동별 주위험유형·보조위험유형을 산출해 risk_type_master.csv를 생성합니다.

권장 실행 환경: Google Colab
입력 파일: final_modelling.csv
출력 파일: risk_type_output/risk_type_master.csv
"""

from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# 1. 경로 설정
# ---------------------------------------------------------------------------
# Google Drive의 실제 폴더 위치와 다르면 BASE_DIR만 수정합니다.
BASE_DIR = Path("/content/drive/MyDrive/modeling")
INPUT_CSV = BASE_DIR / "final_modelling.csv"
OUTPUT_DIR = BASE_DIR / "risk_type_output"
OUTPUT_CSV = OUTPUT_DIR / "risk_type_master.csv"


# ---------------------------------------------------------------------------
# 2. 위험유형 정의
# ---------------------------------------------------------------------------
# 딕셔너리 입력 순서는 점수가 완전히 같은 경우의 우선순위로도 사용됩니다.
TYPE_CONFIG = {
    "공동주택 배송집중형": {
        "indicator": "배송수요",
        "source_column": "배송수요점수_최종",
        "percentile_column": "배송수요위험백분위",
        "ascending_risk": True,
        "policy": "배송시간 분산·공동배송 운영 검토",
    },
    "상권·교통 혼잡형": {
        "indicator": "교통방해",
        "source_column": "교통방해점수",
        "percentile_column": "교통방해위험백분위",
        "ascending_risk": True,
        "policy": "혼잡시간대 하역 회피·탄력 운영",
    },
    "역세권 보행충돌형": {
        "indicator": "보행충돌",
        "source_column": "보행충돌점수_최종",
        "percentile_column": "보행충돌위험백분위",
        "ascending_risk": True,
        "policy": "출퇴근·보행 피크시간 하역 제한",
    },
    "단속반복형": {
        "indicator": "단속반복",
        "source_column": "단속반복점수",
        "percentile_column": "단속반복위험백분위",
        "ascending_risk": True,
        "policy": "탄력 하역권·단속 운영기준 검토",
    },
    "안전취약형": {
        "indicator": "안전취약",
        "source_column": "안전취약점수",
        "percentile_column": "안전취약위험백분위",
        "ascending_risk": True,
        "policy": "등하교·취약계층 이동시간 회피",
    },
    "하역공간 부족형": {
        "indicator": "하역부족",
        "source_column": "하역여유점수",
        "percentile_column": "하역부족위험백분위",
        # 하역여유는 값이 낮을수록 위험하므로 순위를 반대로 계산합니다.
        "ascending_risk": False,
        "policy": "임시 하역면·마이크로 거점 우선 검토",
    },
}


def mount_google_drive() -> None:
    """Colab에서 실행할 때만 Google Drive를 연결합니다."""
    try:
        from google.colab import drive

        drive.mount("/content/drive", force_remount=False)
    except ImportError:
        pass


def read_csv_auto(path: Path, **kwargs) -> pd.DataFrame:
    """UTF-8 또는 CP949 CSV를 자동으로 읽습니다."""
    for encoding in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return pd.read_csv(path, encoding=encoding, **kwargs)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("csv", b"", 0, 1, f"인코딩을 확인할 수 없습니다: {path}")


def require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    """필수 컬럼 누락 여부를 검사합니다."""
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"입력 파일에 필요한 컬럼이 없습니다: {missing}")


def choose_existing_cluster_type(df: pd.DataFrame) -> pd.Series:
    """기존 K-Means 유형명이 저장된 컬럼을 찾아 반환합니다."""
    for candidate in ("위험유형", "위험유형모델", "군집유형"):
        if candidate in df.columns:
            return df[candidate].fillna("")
    return pd.Series([""] * len(df), index=df.index)


def create_risk_type_master(input_csv: Path, output_csv: Path) -> pd.DataFrame:
    """6개 지표 백분위로 행정동별 위험유형을 산출합니다."""
    df = read_csv_auto(input_csv, dtype={"행정동코드": "string"})

    required = [
        "행정동코드",
        "시군구",
        "행정동",
        "DLFI_최종점수",
        "고위험여부",
        *[config["source_column"] for config in TYPE_CONFIG.values()],
    ]
    require_columns(df, required)

    if len(df) != 82:
        print(f"[주의] 현재 입력 행정동은 {len(df)}개입니다. 기존 기준은 82개입니다.")

    # 숫자형 변환과 결측 검사
    numeric_columns = [
        "DLFI_최종점수",
        *[config["source_column"] for config in TYPE_CONFIG.values()],
    ]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    missing_scores = df[numeric_columns].isna().sum()
    if missing_scores.sum() > 0:
        raise ValueError(
            "점수 컬럼에 결측 또는 숫자 변환 실패가 있습니다:\n"
            + missing_scores[missing_scores > 0].to_string()
        )

    # 지표별 위험방향 백분위 계산
    for config in TYPE_CONFIG.values():
        source = config["source_column"]
        target = config["percentile_column"]
        if config["ascending_risk"]:
            percentile = df[source].rank(method="average", pct=True, ascending=True)
        else:
            percentile = df[source].rank(method="average", pct=True, ascending=False)
        df[target] = (percentile * 100).round(1)

    type_names = list(TYPE_CONFIG)
    percentile_columns = [TYPE_CONFIG[name]["percentile_column"] for name in type_names]

    result_rows = []
    existing_cluster_type = choose_existing_cluster_type(df)

    # 원본에 순위가 있으면 유지하고, 없으면 DLFI 기준으로 새로 계산합니다.
    if "순위" in df.columns:
        dlfi_rank = pd.to_numeric(df["순위"], errors="coerce")
    else:
        dlfi_rank = df["DLFI_최종점수"].rank(method="min", ascending=False)

    for index, row in df.iterrows():
        # stable 정렬을 사용해 동점이면 TYPE_CONFIG 순서를 유지합니다.
        ordered_types = sorted(
            type_names,
            key=lambda type_name: -float(row[TYPE_CONFIG[type_name]["percentile_column"]]),
        )
        primary_type, secondary_type = ordered_types[:2]
        primary = TYPE_CONFIG[primary_type]
        secondary = TYPE_CONFIG[secondary_type]

        primary_percentile = float(row[primary["percentile_column"]])
        secondary_percentile = float(row[secondary["percentile_column"]])
        clarity = min(95.0, 50.0 + (primary_percentile - secondary_percentile) * 0.5)

        result_rows.append(
            {
                "행정동코드": row["행정동코드"],
                "시군구": row["시군구"],
                "행정동": row["행정동"],
                "DLFI_순위": int(dlfi_rank.loc[index]),
                "DLFI": round(float(row["DLFI_최종점수"]), 2),
                "고위험여부": row["고위험여부"],
                "군집": row["군집"] if "군집" in df.columns else "",
                "기존군집유형": existing_cluster_type.loc[index],
                "주위험유형": primary_type,
                "보조위험유형": secondary_type,
                "주요근거지표": primary["indicator"],
                "보조근거지표": secondary["indicator"],
                "주요원점수": round(float(row[primary["source_column"]]), 2),
                "보조원점수": round(float(row[secondary["source_column"]]), 2),
                "주요위험백분위": round(primary_percentile, 1),
                "보조위험백분위": round(secondary_percentile, 1),
                "분류명확도": round(clarity, 1),
                "권장관리방향": primary["policy"],
                **{
                    config["percentile_column"]: round(float(row[config["percentile_column"]]), 1)
                    for config in TYPE_CONFIG.values()
                },
                "분류방식": "6개 지표 행정동 백분위 기반 세분화 + 기존 K-Means 군집 보조",
                "기준입력파일": input_csv.name,
            }
        )

    result = pd.DataFrame(result_rows).sort_values(
        ["DLFI_순위", "행정동코드"], kind="stable"
    )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_csv, index=False, encoding="utf-8-sig")

    print(f"[완료] {output_csv}")
    print(f"- 행정동 수: {len(result)}")
    print("- 위험유형 분포")
    print(result["주위험유형"].value_counts().reindex(type_names, fill_value=0))
    return result


if __name__ == "__main__":
    mount_google_drive()
    create_risk_type_master(INPUT_CSV, OUTPUT_CSV)
