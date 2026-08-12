"""D-Curb Guardian 기능 2: 행정동 위험유형 자동 분류.

최종 기획 기준
1. DLFI의 6개 세부 지표를 행정동 백분위 위험점수(0~100)로 표준화
2. 행정동별 위험요인 TOP 3 추출
3. TOP 3가 모두 70점 이상이면 복합위험형
4. 그 외에는 가장 높은 지표로 6개 기본 유형 부여
5. 공동주택·상권·역세권 접두어는 실제 보조지표가 있을 때만 결합
6. 기존 K-Means 결과는 유형 결정이 아닌 보조 검증 정보로만 보존

권장 실행
    python 01_create_risk_type_master.py

로컬 검증 예시
    python 01_create_risk_type_master.py \
        --input final_modelling.csv \
        --output-dir ./feature2_output
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from dcurb_config import (
    FEATURE2_DIR,
    FINAL_MODELLING_CSV,
    REGIONAL_CONTEXT_CSV,
)


COMPOSITE_THRESHOLD = 70.0
STRONG_BASE_THRESHOLD = 75.0
TYPE_SYSTEM_VERSION = "기능2-v2.0"

# 동점이면 아래 순서를 우선합니다. 순서는 정책 개입의 직접성을 기준으로 고정합니다.
TYPE_CONFIG = {
    "하역공간 부족형": {
        "factor": "하역공간 부족",
        "source": "하역여유점수",
        "standardized": "하역공간부족위험점수",
        "higher_is_risk": False,
        "policy": "임시 하역면·공영주차장 유휴면·마이크로 거점 우선 검토",
    },
    "보행충돌형": {
        "factor": "보행충돌",
        "source": "보행충돌점수_최종",
        "standardized": "보행충돌위험점수",
        "higher_is_risk": True,
        "policy": "보행 피크시간 하역 회피·보행안전 완충구간 검토",
    },
    "안전취약형": {
        "factor": "안전취약",
        "source": "안전취약점수",
        "standardized": "안전취약위험점수",
        "higher_is_risk": True,
        "policy": "등하교·취약계층 이동시간 회피·보호구역 후보지 제외",
    },
    "단속반복형": {
        "factor": "단속반복",
        "source": "단속반복점수",
        "standardized": "단속반복위험점수",
        "higher_is_risk": True,
        "policy": "상습구간 탄력 하역권·허용시간·안내표지 정비 검토",
    },
    "교통방해형": {
        "factor": "교통방해",
        "source": "교통방해점수",
        "standardized": "교통방해위험점수",
        "higher_is_risk": True,
        "policy": "혼잡시간대 하역 회피·차로 점유 최소화·운영시간 조정",
    },
    "배송수요 과밀형": {
        "factor": "배송수요",
        "source": "배송수요점수_최종",
        "standardized": "배송수요위험점수",
        "higher_is_risk": True,
        "policy": "배송시간 분산·공동배송·물량 집중시간 조정 검토",
    },
}

FACTOR_TO_TYPE = {
    config["factor"]: type_name for type_name, config in TYPE_CONFIG.items()
}

FACTOR_SHORT_NAME = {
    "배송수요": "배송수요",
    "하역공간 부족": "하역부족",
    "단속반복": "단속반복",
    "보행충돌": "보행충돌",
    "교통방해": "교통방해",
    "안전취약": "안전취약",
}

REGIONAL_CONTEXT_CONFIG = {
    "공동주택": {
        "candidate_columns": [
            "공동주택세대비중",
            "공동주택_세대비중",
            "공동주택비중",
        ],
        "threshold": 70.0,
        "prefix": "공동주택",
    },
    "상권": {
        "candidate_columns": [
            "상가수백분위",
            "상가수_백분위",
            "상권밀도백분위",
        ],
        "threshold": 70.0,
        "prefix": "상권",
    },
    "역세권": {
        "candidate_columns": [
            "대중교통승하차백분위",
            "대중교통_승하차백분위",
            "도시철도승하차백분위",
        ],
        "threshold": 70.0,
        "prefix": "역세권",
    },
}


def mount_google_drive() -> None:
    """Google Colab에서 실행할 때만 Drive를 연결합니다."""
    try:
        from google.colab import drive

        drive.mount("/content/drive", force_remount=False)
    except ImportError:
        pass


def read_csv_auto(path: Path, **kwargs) -> pd.DataFrame:
    """UTF-8 계열 또는 CP949 CSV를 읽습니다."""
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return pd.read_csv(path, encoding=encoding, **kwargs)
        except UnicodeDecodeError as error:
            last_error = error
    raise ValueError(f"CSV 인코딩을 확인할 수 없습니다: {path}") from last_error


def require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"입력 파일에 필요한 컬럼이 없습니다: {missing}")


def normalize_code(series: pd.Series) -> pd.Series:
    return series.astype("string").str.replace(r"\.0$", "", regex=True)


def risk_percentile(series: pd.Series, higher_is_risk: bool) -> pd.Series:
    """서로 다른 지표 분포를 비교할 수 있도록 위험방향 백분위로 변환합니다."""
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.isna().any():
        raise ValueError(f"점수 컬럼에 결측 또는 숫자 변환 실패가 있습니다: {series.name}")
    return (
        numeric.rank(
            method="average",
            pct=True,
            ascending=higher_is_risk,
        )
        * 100
    ).round(1)


def load_regional_context(path: Path | None) -> pd.DataFrame | None:
    """선택 보조데이터를 읽습니다. 없으면 지역특성 접두어를 산출하지 않습니다."""
    if path is None or not path.exists():
        return None

    context = read_csv_auto(path, dtype={"행정동코드": "string"})
    require_columns(context, ["행정동코드"])
    context["행정동코드"] = normalize_code(context["행정동코드"])
    if context["행정동코드"].duplicated().any():
        duplicated = context.loc[
            context["행정동코드"].duplicated(keep=False), "행정동코드"
        ].tolist()
        raise ValueError(f"regional_context.csv 행정동코드 중복: {duplicated}")
    return context


def attach_regional_context(
    df: pd.DataFrame, context: pd.DataFrame | None
) -> tuple[pd.DataFrame, list[tuple[str, str, float, str]]]:
    """실제 존재하는 지역특성 컬럼만 병합하고 사용 명세를 반환합니다."""
    if context is None:
        return df, []

    selected_specs: list[tuple[str, str, float, str]] = []
    merge_columns = ["행정동코드"]
    for context_name, config in REGIONAL_CONTEXT_CONFIG.items():
        column = next(
            (
                candidate
                for candidate in config["candidate_columns"]
                if candidate in context.columns
            ),
            None,
        )
        if column:
            selected_specs.append(
                (
                    context_name,
                    column,
                    float(config["threshold"]),
                    str(config["prefix"]),
                )
            )
            merge_columns.append(column)

    if not selected_specs:
        return df, []

    merged = df.merge(
        context[merge_columns],
        on="행정동코드",
        how="left",
        validate="one_to_one",
    )
    return merged, selected_specs


def regional_prefix(
    row: pd.Series, specs: list[tuple[str, str, float, str]]
) -> tuple[str, str]:
    """임계값을 충족한 실제 지역특성 중 가장 높은 근거 하나를 선택합니다."""
    candidates: list[tuple[float, str, str]] = []
    for _, column, threshold, prefix in specs:
        value = pd.to_numeric(pd.Series([row.get(column)]), errors="coerce").iloc[0]
        if pd.notna(value) and float(value) >= threshold:
            candidates.append((float(value), prefix, column))
    if not candidates:
        if specs:
            return "", "연결된 지역특성 지표가 기준 미충족"
        return "", "세대·상가·승하차 보조데이터 미연결"
    value, prefix, column = max(candidates, key=lambda item: item[0])
    return prefix, f"{column} {value:.1f}점"


def make_display_type(
    base_type: str,
    is_composite: bool,
    top_factors: list[str],
    prefix: str,
) -> str:
    if is_composite:
        factor_label = "·".join(FACTOR_SHORT_NAME[factor] for factor in top_factors[:2])
        core = f"{factor_label} 복합위험형"
    else:
        core = base_type
    return f"{prefix} {core}".strip()


def make_interpretation(
    region: str,
    display_type: str,
    top_factors: list[str],
    top_scores: list[float],
) -> str:
    factors = ", ".join(
        f"{FACTOR_SHORT_NAME[factor]} {score:.1f}점"
        for factor, score in zip(top_factors, top_scores)
    )
    return f"{region}은(는) {display_type}이며, 주요 위험요인은 {factors}입니다."


def create_rules_table() -> pd.DataFrame:
    rows = [
        {
            "위험유형": "복합위험형",
            "판정조건": "표준화 위험점수 TOP 3가 모두 70점 이상",
            "기준점수": COMPOSITE_THRESHOLD,
            "대표지표": "TOP 3 위험요인",
            "정책연결": "TOP 3 기본 정책을 중복 제거해 결합",
            "대시보드대표유형": "예",
            "KMeans역할": "판정에 사용하지 않음·패턴 검증용",
        }
    ]
    for type_name, config in TYPE_CONFIG.items():
        rows.append(
            {
                "위험유형": type_name,
                "판정조건": (
                    "복합위험형이 아니며 해당 지표가 6개 중 가장 높음; "
                    "75점 이상이면 강한 판정"
                ),
                "기준점수": STRONG_BASE_THRESHOLD,
                "대표지표": config["factor"],
                "정책연결": config["policy"],
                "대시보드대표유형": "예",
                "KMeans역할": "판정에 사용하지 않음·패턴 검증용",
            }
        )
    return pd.DataFrame(rows)


def create_risk_type_master(
    input_csv: Path,
    output_dir: Path,
    regional_context_csv: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = read_csv_auto(input_csv, dtype={"행정동코드": "string"})
    required = [
        "행정동코드",
        "시군구",
        "행정동",
        "DLFI_최종점수",
        "고위험여부",
        *[config["source"] for config in TYPE_CONFIG.values()],
    ]
    require_columns(df, required)
    df["행정동코드"] = normalize_code(df["행정동코드"])

    if df["행정동코드"].duplicated().any():
        raise ValueError("입력 파일에 중복 행정동코드가 있습니다.")
    if len(df) != 82:
        print(f"[주의] 입력 행정동 수는 {len(df)}개입니다. 기준 데이터는 82개입니다.")

    numeric_columns = [
        "DLFI_최종점수",
        *[config["source"] for config in TYPE_CONFIG.values()],
    ]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    missing = df[numeric_columns].isna().sum()
    if missing.sum():
        raise ValueError(
            "점수 컬럼에 결측 또는 숫자 변환 실패가 있습니다:\n"
            + missing[missing > 0].to_string()
        )

    # 점수가 낮을수록 위험한 하역여유를 포함해 위험방향을 통일합니다.
    for config in TYPE_CONFIG.values():
        df[config["standardized"]] = risk_percentile(
            df[config["source"]],
            higher_is_risk=bool(config["higher_is_risk"]),
        )

    context = load_regional_context(regional_context_csv)
    df, regional_specs = attach_regional_context(df, context)

    if "순위" in df.columns:
        dlfi_rank = pd.to_numeric(df["순위"], errors="coerce")
    else:
        dlfi_rank = df["DLFI_최종점수"].rank(method="min", ascending=False)

    existing_kmeans_type = (
        df["위험유형"].fillna("").astype(str)
        if "위험유형" in df.columns
        else pd.Series([""] * len(df), index=df.index)
    )
    existing_kmeans_cluster = (
        df["군집"].fillna("").astype(str)
        if "군집" in df.columns
        else pd.Series([""] * len(df), index=df.index)
    )

    def optional_value(row: pd.Series, column: str, default=""):
        value = row.get(column, default)
        return default if pd.isna(value) else value

    factor_config = {
        config["factor"]: config for config in TYPE_CONFIG.values()
    }
    factors = list(factor_config)
    result_rows: list[dict] = []

    for index, row in df.iterrows():
        ordered_factors = sorted(
            factors,
            key=lambda factor: (
                -float(row[factor_config[factor]["standardized"]]),
                factors.index(factor),
            ),
        )
        top_factors = ordered_factors[:3]
        top_scores = [
            float(row[factor_config[factor]["standardized"]])
            for factor in top_factors
        ]
        is_composite = all(score >= COMPOSITE_THRESHOLD for score in top_scores)

        base_type = "복합위험형" if is_composite else FACTOR_TO_TYPE[top_factors[0]]
        prefix, prefix_evidence = regional_prefix(row, regional_specs)
        display_type = make_display_type(
            base_type=base_type,
            is_composite=is_composite,
            top_factors=top_factors,
            prefix=prefix,
        )

        if is_composite:
            policies = [
                FACTOR_TO_TYPE[factor] for factor in top_factors
            ]
            policy_text = " + ".join(
                TYPE_CONFIG[type_name]["policy"] for type_name in policies
            )
            decision_strength = "복합판정"
            composite_evidence = (
                f"TOP3 최저점 {min(top_scores):.1f}점 ≥ "
                f"{COMPOSITE_THRESHOLD:.0f}점"
            )
        else:
            policy_text = TYPE_CONFIG[base_type]["policy"]
            decision_strength = (
                "강한 기본유형"
                if top_scores[0] >= STRONG_BASE_THRESHOLD
                else "관찰 기본유형"
            )
            composite_evidence = (
                f"TOP3 최저점 {min(top_scores):.1f}점 < "
                f"{COMPOSITE_THRESHOLD:.0f}점"
            )

        region_name = f"{row['시군구']} {row['행정동']}"
        result_rows.append(
            {
                "행정동코드": row["행정동코드"],
                "시군구": row["시군구"],
                "행정동": row["행정동"],
                "DLFI_순위": int(dlfi_rank.loc[index]),
                "DLFI": round(float(row["DLFI_최종점수"]), 2),
                "고위험여부": row["고위험여부"],
                # 대시보드가 사용하는 단 하나의 대표 유형 컬럼
                "위험유형": display_type,
                "기본위험유형": base_type,
                "복합위험여부": "예" if is_composite else "아니오",
                "복합판정근거": composite_evidence,
                "판정강도": decision_strength,
                "지역특성태그": prefix if prefix else "미산출",
                "지역특성근거": prefix_evidence,
                "주요위험요인1": top_factors[0],
                "주요위험요인2": top_factors[1],
                "주요위험요인3": top_factors[2],
                "주요위험점수1": round(top_scores[0], 1),
                "주요위험점수2": round(top_scores[1], 1),
                "주요위험점수3": round(top_scores[2], 1),
                "한줄자동해석": make_interpretation(
                    region_name, display_type, top_factors, top_scores
                ),
                "권장정책": policy_text,
                **{
                    config["standardized"]: round(
                        float(row[config["standardized"]]), 1
                    )
                    for config in TYPE_CONFIG.values()
                },
                "기존KMeans군집_보조": existing_kmeans_cluster.loc[index],
                "기존KMeans유형_보조": existing_kmeans_type.loc[index],
                "KMeans활용구분": "보조 검증용·최종 유형 판정 미사용",
                "공식예측모델_보조": optional_value(row, "공식예측모델"),
                "고위험예측확률_보조": optional_value(row, "고위험예측확률"),
                "예측일치_보조": optional_value(row, "예측일치"),
                "SHAP_TOP1_변수_보조": optional_value(row, "SHAP_TOP1_변수"),
                "SHAP_TOP1_값_보조": optional_value(row, "SHAP_TOP1_값"),
                "SHAP_TOP2_변수_보조": optional_value(row, "SHAP_TOP2_변수"),
                "SHAP_TOP2_값_보조": optional_value(row, "SHAP_TOP2_값"),
                "SHAP_TOP3_변수_보조": optional_value(row, "SHAP_TOP3_변수"),
                "SHAP_TOP3_값_보조": optional_value(row, "SHAP_TOP3_값"),
                "모델추천정책_원본": optional_value(row, "추천정책_텍스트"),
                "표준화방법": "82개 행정동 내 위험방향 백분위 0~100",
                "유형체계버전": TYPE_SYSTEM_VERSION,
                "기준입력파일": input_csv.name,
            }
        )

    result = (
        pd.DataFrame(result_rows)
        .sort_values(["DLFI_순위", "행정동코드"], kind="stable")
        .reset_index(drop=True)
    )
    rules = create_rules_table()

    output_dir.mkdir(parents=True, exist_ok=True)
    master_path = output_dir / "risk_type_master.csv"
    rules_path = output_dir / "risk_type_rules.csv"
    result.to_csv(master_path, index=False, encoding="utf-8-sig")
    rules.to_csv(rules_path, index=False, encoding="utf-8-sig")

    print(f"[완료] {master_path}")
    print(f"[완료] {rules_path}")
    print(f"- 행정동 수: {len(result)}")
    print("- 대표 기본유형 분포")
    print(result["기본위험유형"].value_counts())
    print(
        "- 지역특성 접두어:",
        "적용" if regional_specs else "미적용(실제 보조데이터 미연결)",
    )
    return result, rules


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=FINAL_MODELLING_CSV,
        help="final_modelling.csv 경로",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=FEATURE2_DIR,
        help="기능 2 결과 저장 폴더",
    )
    parser.add_argument(
        "--regional-context",
        type=Path,
        default=REGIONAL_CONTEXT_CSV,
        help="선택 보조파일 regional_context.csv 경로",
    )
    parser.add_argument(
        "--skip-mount",
        action="store_true",
        help="Colab Drive 자동 마운트 생략",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if not args.skip_mount:
        mount_google_drive()
    context_path = args.regional_context if args.regional_context.exists() else None
    create_risk_type_master(
        input_csv=args.input,
        output_dir=args.output_dir,
        regional_context_csv=context_path,
    )
