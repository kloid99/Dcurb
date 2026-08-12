"""
기능 3. 정책 What-if 시뮬레이터 및 정책 패키지 추천

- 기준 데이터: final_modelling.csv
- 단독 실행: streamlit run feature3_policy_whatif_streamlit.py
- 메인 앱 결합:
    from feature3_policy_whatif_streamlit import render_policy_simulator
    render_policy_simulator(df)

정책 효과값은 실증값이 아니라 초기 MVP용 규칙값입니다.
향후 시범사업 결과나 전문가 합의값으로 POLICY_RULES만 교체하면 됩니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# -----------------------------------------------------------------------------
# 1. 공통 데이터 정의
# -----------------------------------------------------------------------------
REQUIRED_COLUMNS: Tuple[str, ...] = (
    "행정동코드",
    "시군구",
    "행정동",
    "DLFI_최종점수",
    "배송수요점수_최종",
    "교통방해점수",
    "보행충돌점수_최종",
    "단속반복점수",
    "안전취약점수",
    "하역여유점수",
    "하역부족위험",
    "위험유형",
    "우선순위등급",
    "추천정책_텍스트",
)

BASE_SCORE_COLUMNS: Tuple[str, ...] = (
    "배송수요점수_최종",
    "교통방해점수",
    "보행충돌점수_최종",
    "단속반복점수",
    "안전취약점수",
)

DISPLAY_LABELS: Mapping[str, str] = {
    "배송수요점수_최종": "배송수요",
    "교통방해점수": "교통방해",
    "보행충돌점수_최종": "보행충돌",
    "단속반복점수": "단속반복",
    "안전취약점수": "안전취약",
    "하역부족위험": "하역공간 부족",
}

COST_VALUE = {"낮음": 1.0, "중간": 2.0, "중간~높음": 2.5, "높음": 3.0}
DIFFICULTY_VALUE = {"낮음": 1.0, "중간": 2.0, "높음": 3.0}
SPEED_VALUE = {"단기": 3.0, "중기": 2.0, "장기": 1.0}


@dataclass(frozen=True)
class PolicyRule:
    name: str
    description: str
    cost: str
    difficulty: str
    duration: str
    impacts: Mapping[str, Tuple[str, float]]
    # impacts 값 형식
    # ("absolute_down", 15): 해당 점수를 최대 15점 감소
    # ("percent_down", 0.12): 해당 점수를 최대 12% 감소
    # ("absolute_up", 25): 하역여유 등 긍정 점수를 최대 25점 증가


POLICY_RULES: Mapping[str, PolicyRule] = {
    "탄력 하역공간 운영": PolicyRule(
        name="탄력 하역공간 운영",
        description="공영주차장·도로 일부를 시간대별 하역공간으로 전환",
        cost="중간",
        difficulty="중간",
        duration="중기",
        impacts={
            "하역여유점수": ("absolute_up", 25.0),
            "단속반복점수": ("absolute_down", 15.0),
            "교통방해점수": ("absolute_down", 10.0),
        },
    ),
    "배송시간 분산": PolicyRule(
        name="배송시간 분산",
        description="혼잡·보행 집중시간을 피해 배송시간대를 분산",
        cost="낮음",
        difficulty="낮음",
        duration="단기",
        impacts={
            "교통방해점수": ("percent_down", 0.12),
            "보행충돌점수_최종": ("percent_down", 0.10),
            "단속반복점수": ("percent_down", 0.05),
        },
    ),
    "소형 마이크로 하역거점": PolicyRule(
        name="소형 마이크로 하역거점",
        description="배송차량 환적·공동배송을 위한 소규모 거점 설치",
        cost="중간~높음",
        difficulty="높음",
        duration="중기",
        impacts={
            "하역여유점수": ("absolute_up", 35.0),
            "배송수요점수_최종": ("percent_down", 0.08),
            "교통방해점수": ("percent_down", 0.08),
        },
    ),
    "특정 시간대 하역 제한": PolicyRule(
        name="특정 시간대 하역 제한",
        description="등하교·출퇴근 등 보행·교통 집중시간 하역 제한",
        cost="낮음",
        difficulty="중간",
        duration="단기",
        impacts={
            "보행충돌점수_최종": ("percent_down", 0.15),
            "안전취약점수": ("percent_down", 0.10),
            "교통방해점수": ("percent_down", 0.05),
        },
    ),
    "CCTV 재배치": PolicyRule(
        name="CCTV 재배치",
        description="상습 불법정차 구간 중심으로 단속자원 재배치",
        cost="중간",
        difficulty="중간",
        duration="중기",
        impacts={"단속반복점수": ("percent_down", 0.10)},
    ),
    "상습구간 표지 강화": PolicyRule(
        name="상습구간 표지 강화",
        description="배송 가능시간·금지구간·우회정보를 현장 표지로 안내",
        cost="낮음",
        difficulty="낮음",
        duration="단기",
        impacts={
            "단속반복점수": ("percent_down", 0.07),
            "교통방해점수": ("percent_down", 0.04),
        },
    ),
    "보호구역 완충구간": PolicyRule(
        name="보호구역 완충구간",
        description="학교·어린이·노인보호구역 주변 배송차량 완충공간 조성",
        cost="중간",
        difficulty="높음",
        duration="중기",
        impacts={
            "보행충돌점수_최종": ("percent_down", 0.20),
            "안전취약점수": ("percent_down", 0.18),
        },
    ),
    "시민·상인 사전안내": PolicyRule(
        name="시민·상인 사전안내",
        description="정책 시행 전 배송기사·상인·주민에게 운영규칙 안내",
        cost="낮음",
        difficulty="낮음",
        duration="단기",
        impacts={
            "단속반복점수": ("percent_down", 0.04),
            "교통방해점수": ("percent_down", 0.03),
            "보행충돌점수_최종": ("percent_down", 0.03),
        },
    ),
}


# -----------------------------------------------------------------------------
# 2. 데이터 로드·검증
# -----------------------------------------------------------------------------
def find_default_csv() -> Optional[Path]:
    """팀 파일명 표기 차이를 고려해 공통 CSV 경로를 자동 탐색합니다."""
    candidates = (
        Path("final_modelling.csv"),
        Path("final_modeling.csv"),
        Path("data/final_modelling.csv"),
        Path("data/final_modeling.csv"),
    )
    return next((path for path in candidates if path.exists()), None)


@st.cache_data(show_spinner=False)
def load_data(csv_path: str) -> pd.DataFrame:
    return pd.read_csv(csv_path, dtype={"행정동코드": "string"})


def validate_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError("필수 칼럼이 없습니다: " + ", ".join(missing))

    clean = df.copy()
    clean["행정동코드"] = clean["행정동코드"].astype("string")

    numeric_columns = (
        "DLFI_최종점수",
        "배송수요점수_최종",
        "교통방해점수",
        "보행충돌점수_최종",
        "단속반복점수",
        "안전취약점수",
        "하역여유점수",
        "하역부족위험",
    )
    for column in numeric_columns:
        clean[column] = pd.to_numeric(clean[column], errors="coerce")

    invalid_rows = clean[list(numeric_columns)].isna().any(axis=1)
    if invalid_rows.any():
        clean = clean.loc[~invalid_rows].copy()

    if clean.empty:
        raise ValueError("수치 칼럼을 변환한 뒤 사용할 수 있는 행이 없습니다.")

    clean["하역여유점수"] = clean["하역여유점수"].clip(0, 100)
    clean["하역부족위험"] = (100 - clean["하역여유점수"]).clip(0, 100)
    return clean


# -----------------------------------------------------------------------------
# 3. What-if 계산 함수
# -----------------------------------------------------------------------------
def row_to_metrics(row: pd.Series) -> Dict[str, float]:
    return {
        "배송수요점수_최종": float(row["배송수요점수_최종"]),
        "교통방해점수": float(row["교통방해점수"]),
        "보행충돌점수_최종": float(row["보행충돌점수_최종"]),
        "단속반복점수": float(row["단속반복점수"]),
        "안전취약점수": float(row["안전취약점수"]),
        "하역여유점수": float(row["하역여유점수"]),
    }


def calculate_component_dlfi(metrics: Mapping[str, float]) -> float:
    """
    final_modelling.csv 82개 행 중 이상치 1건을 제외한 81개 행에서 재현되는 산식.
    DLFI = 배송수요 + 교통방해 + 보행충돌 + 단속반복 + 안전취약 - 하역여유
    """
    score = sum(float(metrics[column]) for column in BASE_SCORE_COLUMNS)
    score -= float(metrics["하역여유점수"])
    return round(max(score, 0.0), 2)


def apply_policy(
    metrics: Mapping[str, float],
    policy_name: str,
    intensity: float = 1.0,
) -> Dict[str, float]:
    if policy_name not in POLICY_RULES:
        raise KeyError(f"정의되지 않은 정책입니다: {policy_name}")

    intensity = float(np.clip(intensity, 0.0, 1.0))
    updated = {key: float(value) for key, value in metrics.items()}
    rule = POLICY_RULES[policy_name]

    for column, (method, amount) in rule.impacts.items():
        before = updated[column]
        if method == "absolute_down":
            after = before - amount * intensity
        elif method == "percent_down":
            after = before * (1 - amount * intensity)
        elif method == "absolute_up":
            after = before + amount * intensity
        else:
            raise ValueError(f"지원하지 않는 효과 방식입니다: {method}")
        updated[column] = round(float(np.clip(after, 0.0, 100.0)), 4)

    return updated


def simulate_policies(
    row: pd.Series,
    selected_policies: Sequence[str],
    intensity: float,
) -> Dict[str, object]:
    before_metrics = row_to_metrics(row)
    after_metrics = before_metrics.copy()

    for policy_name in selected_policies:
        after_metrics = apply_policy(after_metrics, policy_name, intensity)

    component_before = calculate_component_dlfi(before_metrics)
    component_after = calculate_component_dlfi(after_metrics)
    improvement = round(max(component_before - component_after, 0.0), 2)

    # 공식 DLFI는 데이터셋 값을 기준으로 유지하고, 세부지표 산식으로 계산한 개선폭만 반영합니다.
    official_before = float(row["DLFI_최종점수"])
    official_after = round(max(official_before - improvement, 0.0), 2)
    improvement_rate = round((improvement / official_before) * 100, 1) if official_before > 0 else 0.0

    return {
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "before_dlfi": round(official_before, 2),
        "after_dlfi": official_after,
        "reduction": improvement,
        "reduction_rate": improvement_rate,
        "component_before": component_before,
        "component_after": component_after,
    }


def single_policy_results(row: pd.Series, intensity: float) -> pd.DataFrame:
    records: List[Dict[str, object]] = []
    for policy_name, rule in POLICY_RULES.items():
        result = simulate_policies(row, [policy_name], intensity)
        records.append(
            {
                "정책": policy_name,
                "적용 후 DLFI": result["after_dlfi"],
                "DLFI 감소": result["reduction"],
                "감소율(%)": result["reduction_rate"],
                "비용": rule.cost,
                "난이도": rule.difficulty,
                "시행기간": rule.duration,
                "설명": rule.description,
            }
        )
    return pd.DataFrame(records)


def minmax_score(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").fillna(0.0)
    minimum, maximum = float(values.min()), float(values.max())
    if np.isclose(maximum, minimum):
        normalized = pd.Series(np.full(len(values), 50.0), index=values.index)
    else:
        normalized = (values - minimum) / (maximum - minimum) * 100
    return normalized if higher_is_better else 100 - normalized


def rank_policy_results(results: pd.DataFrame, criterion: str) -> pd.DataFrame:
    ranked = results.copy()
    ranked["효과점수"] = minmax_score(ranked["DLFI 감소"])

    cost_numeric = ranked["비용"].map(COST_VALUE).astype(float)
    difficulty_numeric = ranked["난이도"].map(DIFFICULTY_VALUE).astype(float)
    speed_numeric = ranked["시행기간"].map(SPEED_VALUE).astype(float)

    efficiency_raw = ranked["DLFI 감소"] / cost_numeric.replace(0, np.nan)
    ranked["비용효율"] = minmax_score(efficiency_raw.fillna(0))
    ranked["실행용이성"] = minmax_score(difficulty_numeric, higher_is_better=False)
    ranked["시행속도"] = minmax_score(speed_numeric)

    weight_map = {
        "균형형": (0.40, 0.25, 0.20, 0.15),
        "효과 우선": (0.70, 0.10, 0.10, 0.10),
        "비용 우선": (0.25, 0.55, 0.10, 0.10),
        "빠른 실행 우선": (0.25, 0.15, 0.20, 0.40),
    }
    effect_w, cost_w, ease_w, speed_w = weight_map[criterion]
    ranked["종합 정책점수"] = (
        ranked["효과점수"] * effect_w
        + ranked["비용효율"] * cost_w
        + ranked["실행용이성"] * ease_w
        + ranked["시행속도"] * speed_w
    ).round(1)

    ranked = ranked.sort_values(
        ["종합 정책점수", "DLFI 감소"], ascending=[False, False]
    ).reset_index(drop=True)
    ranked.insert(0, "추천순위", np.arange(1, len(ranked) + 1))
    return ranked


def dominant_risks(row: pd.Series, top_n: int = 3) -> List[Tuple[str, float]]:
    risk_values = {
        "배송수요": float(row["배송수요점수_최종"]),
        "교통방해": float(row["교통방해점수"]),
        "보행충돌": float(row["보행충돌점수_최종"]),
        "단속반복": float(row["단속반복점수"]),
        "안전취약": float(row["안전취약점수"]),
        "하역공간 부족": float(row["하역부족위험"]),
    }
    return sorted(risk_values.items(), key=lambda item: item[1], reverse=True)[:top_n]


def build_risk_package(row: pd.Series, ranked: pd.DataFrame) -> List[str]:
    """현재 행정동의 상위 위험요인과 정책점수를 함께 사용해 3단계 패키지를 만듭니다."""
    dominant_names = {name for name, _ in dominant_risks(row, 3)}
    preferred: List[str] = []

    if "하역공간 부족" in dominant_names:
        preferred.extend(["탄력 하역공간 운영", "소형 마이크로 하역거점"])
    if "단속반복" in dominant_names:
        preferred.extend(["상습구간 표지 강화", "CCTV 재배치"])
    if {"보행충돌", "안전취약"} & dominant_names:
        preferred.extend(["특정 시간대 하역 제한", "보호구역 완충구간"])
    if {"교통방해", "배송수요"} & dominant_names:
        preferred.extend(["배송시간 분산", "시민·상인 사전안내"])

    ranked_names = ranked["정책"].tolist()
    ordered = []
    for name in preferred + ranked_names:
        if name not in ordered:
            ordered.append(name)

    # 단기 → 중기 순서가 자연스럽도록, 첫 3개 안에서 시행기간과 점수를 같이 고려합니다.
    score_lookup = ranked.set_index("정책")["종합 정책점수"].to_dict()
    ordered.sort(
        key=lambda name: (
            -SPEED_VALUE[POLICY_RULES[name].duration],
            -score_lookup.get(name, 0),
        )
    )
    return ordered[:3]


# -----------------------------------------------------------------------------
# 4. 시각화
# -----------------------------------------------------------------------------
def make_before_after_chart(result: Mapping[str, object]) -> go.Figure:
    before = result["before_metrics"]
    after = result["after_metrics"]

    columns = [
        "배송수요점수_최종",
        "교통방해점수",
        "보행충돌점수_최종",
        "단속반복점수",
        "안전취약점수",
    ]
    labels = [DISPLAY_LABELS[column] for column in columns] + ["하역공간 부족"]
    before_values = [before[column] for column in columns] + [100 - before["하역여유점수"]]
    after_values = [after[column] for column in columns] + [100 - after["하역여유점수"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(name="적용 전", x=labels, y=before_values, text=np.round(before_values, 1), textposition="outside"))
    fig.add_trace(go.Bar(name="적용 후", x=labels, y=after_values, text=np.round(after_values, 1), textposition="outside"))
    fig.update_layout(
        barmode="group",
        height=430,
        margin=dict(l=10, r=10, t=50, b=10),
        yaxis=dict(title="위험점수", range=[0, 112]),
        legend=dict(orientation="h", y=1.12, x=0),
        hovermode="x unified",
    )
    return fig


def make_dlfi_gauge(before_dlfi: float, after_dlfi: float) -> go.Figure:
    max_axis = max(400.0, before_dlfi * 1.15)
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=after_dlfi,
            number={"suffix": "점", "valueformat": ".2f"},
            delta={"reference": before_dlfi, "relative": False, "valueformat": ".2f"},
            title={"text": "정책 적용 후 DLFI"},
            gauge={
                "axis": {"range": [0, max_axis]},
                "bar": {"thickness": 0.28},
                "threshold": {
                    "line": {"width": 4},
                    "thickness": 0.75,
                    "value": before_dlfi,
                },
            },
        )
    )
    fig.update_layout(height=300, margin=dict(l=25, r=25, t=55, b=10))
    return fig


def metric_change_table(result: Mapping[str, object]) -> pd.DataFrame:
    before = result["before_metrics"]
    after = result["after_metrics"]
    records = []
    for column in BASE_SCORE_COLUMNS:
        records.append(
            {
                "지표": DISPLAY_LABELS[column],
                "적용 전": round(before[column], 2),
                "적용 후": round(after[column], 2),
                "변화": round(after[column] - before[column], 2),
            }
        )

    before_shortage = 100 - before["하역여유점수"]
    after_shortage = 100 - after["하역여유점수"]
    records.append(
        {
            "지표": "하역공간 부족",
            "적용 전": round(before_shortage, 2),
            "적용 후": round(after_shortage, 2),
            "변화": round(after_shortage - before_shortage, 2),
        }
    )
    return pd.DataFrame(records)


# -----------------------------------------------------------------------------
# 5. Streamlit 화면
# -----------------------------------------------------------------------------
def inject_local_css() -> None:
    st.markdown(
        """
        <style>
        .feature3-title {font-size: 2rem; font-weight: 800; margin-bottom: .2rem;}
        .feature3-sub {color: #667085; margin-bottom: 1.2rem;}
        .policy-card {border: 1px solid #e4e7ec; border-radius: 14px; padding: 16px; background: #ffffff; margin-bottom: 10px;}
        .policy-rank {font-size: .85rem; font-weight: 800; color: #175cd3;}
        .policy-name {font-size: 1.05rem; font-weight: 800; margin: 4px 0;}
        .policy-meta {font-size: .88rem; color: #667085;}
        .risk-badge {display: inline-block; padding: 5px 10px; margin: 2px 5px 2px 0; border-radius: 999px; background: #eff8ff; color: #175cd3; font-weight: 700;}
        .notice-box {border-left: 4px solid #f79009; background: #fffaeb; padding: 12px 14px; border-radius: 8px; color: #7a2e0e;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def resolve_dataframe(df: Optional[pd.DataFrame], csv_path: Optional[str]) -> pd.DataFrame:
    if df is not None:
        return validate_dataframe(df)

    selected_path = Path(csv_path) if csv_path else find_default_csv()
    if selected_path is None or not selected_path.exists():
        st.error("final_modelling.csv를 찾지 못했습니다. 메인 앱에서 DataFrame을 전달하거나 파일 경로를 지정하세요.")
        st.stop()
    return validate_dataframe(load_data(str(selected_path)))


def render_policy_simulator(
    df: Optional[pd.DataFrame] = None,
    csv_path: Optional[str] = None,
) -> None:
    """메인 앱에서 호출할 기능 3 렌더 함수입니다."""
    inject_local_css()
    data = resolve_dataframe(df, csv_path)

    st.markdown('<div class="feature3-title">정책 What-if 시뮬레이터</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="feature3-sub">행정동별 위험요인을 바탕으로 정책 적용 전후 DLFI를 비교하고 실행 우선순위를 추천합니다.</div>',
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.subheader("시뮬레이션 조건")
        selected_gu = st.selectbox(
            "시군구",
            sorted(data["시군구"].dropna().unique().tolist()),
            key="feature3_selected_gu",
        )
        gu_data = data.loc[data["시군구"] == selected_gu].sort_values("DLFI_최종점수", ascending=False)
        selected_dong = st.selectbox(
            "행정동",
            gu_data["행정동"].tolist(),
            key="feature3_selected_dong",
        )
        criterion = st.selectbox(
            "정책 우선기준",
            ["균형형", "효과 우선", "비용 우선", "빠른 실행 우선"],
            key="feature3_criterion",
        )
        intensity_percent = st.slider(
            "정책 적용 강도",
            min_value=25,
            max_value=100,
            value=100,
            step=25,
            help="초기 규칙의 최대 효과 중 어느 정도가 실제로 나타난다고 가정할지 설정합니다.",
            key="feature3_intensity",
        )
        intensity = intensity_percent / 100

    row = gu_data.loc[gu_data["행정동"] == selected_dong].iloc[0]
    individual = single_policy_results(row, intensity)
    ranked = rank_policy_results(individual, criterion)
    default_package = build_risk_package(row, ranked)

    top_risks = dominant_risks(row, 3)
    top1, top2, top3, top4 = st.columns(4)
    top1.metric("현재 DLFI", f"{row['DLFI_최종점수']:.2f}점")
    top2.metric("위험유형", str(row["위험유형"]))
    top3.metric("우선순위", str(row["우선순위등급"]))
    top4.metric("고위험 예측확률", f"{float(row.get('고위험예측확률', 0)) * 100:.1f}%")

    st.markdown("**주요 위험요인 TOP 3**")
    badge_html = "".join(
        f'<span class="risk-badge">{name} {score:.1f}점</span>' for name, score in top_risks
    )
    st.markdown(badge_html, unsafe_allow_html=True)

    if str(row["위험유형"]).startswith("이상치"):
        st.warning(
            "이 행정동은 원본 모델링 결과에서 이상치로 별도 처리되었습니다. "
            "정책 시뮬레이션은 공식 DLFI 0점을 기준으로 개선폭만 계산하므로 해석에 주의하세요."
        )

    st.divider()
    st.subheader("1. 정책 조합 선택")
    selected_policies = st.multiselect(
        "적용할 정책",
        options=list(POLICY_RULES.keys()),
        default=default_package[:2],
        help="여러 정책은 순차 적용되며 각 지표는 0~100 범위로 제한됩니다.",
        key="feature3_selected_policies",
    )

    if not selected_policies:
        st.info("정책을 한 개 이상 선택하면 적용 전후 결과가 계산됩니다.")
        selected_policies = []

    combined = simulate_policies(row, selected_policies, intensity)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("적용 전 DLFI", f"{combined['before_dlfi']:.2f}점")
    c2.metric(
        "적용 후 DLFI",
        f"{combined['after_dlfi']:.2f}점",
        delta=f"-{combined['reduction']:.2f}점",
        delta_color="inverse",
    )
    c3.metric("예상 감소율", f"{combined['reduction_rate']:.1f}%")
    c4.metric("선택 정책 수", f"{len(selected_policies)}개")

    chart_col, gauge_col = st.columns([1.8, 1])
    with chart_col:
        st.plotly_chart(make_before_after_chart(combined), use_container_width=True)
    with gauge_col:
        st.plotly_chart(
            make_dlfi_gauge(combined["before_dlfi"], combined["after_dlfi"]),
            use_container_width=True,
        )

    with st.expander("세부 지표 변화표", expanded=False):
        st.dataframe(metric_change_table(combined), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("2. 정책별 비교 및 추천")
    visible_columns = [
        "추천순위",
        "정책",
        "적용 후 DLFI",
        "DLFI 감소",
        "감소율(%)",
        "비용",
        "난이도",
        "시행기간",
        "종합 정책점수",
    ]
    st.dataframe(
        ranked[visible_columns],
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "균형형 종합점수 = 효과 40% + 비용효율 25% + 실행용이성 20% + 시행속도 15%. "
        "다른 우선기준을 선택하면 가중치가 자동 변경됩니다."
    )

    st.subheader("3. 단계별 정책 패키지")
    package = build_risk_package(row, ranked)
    package_cols = st.columns(3)
    for index, (column, policy_name) in enumerate(zip(package_cols, package), start=1):
        rule = POLICY_RULES[policy_name]
        score = float(ranked.loc[ranked["정책"] == policy_name, "종합 정책점수"].iloc[0])
        with column:
            st.markdown(
                f"""
                <div class="policy-card">
                    <div class="policy-rank">{index}단계 · {rule.duration}</div>
                    <div class="policy-name">{policy_name}</div>
                    <div class="policy-meta">{rule.description}</div>
                    <hr style="border:none;border-top:1px solid #eaecf0;margin:12px 0;">
                    <div class="policy-meta">비용 {rule.cost} · 난이도 {rule.difficulty} · 추천점수 {score:.1f}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown(
        f"""
        <div class="notice-box">
        <b>현재 모델의 기존 추천:</b> {row['추천정책_텍스트']}<br>
        <b>What-if 추천:</b> {' → '.join(package)}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()
    st.subheader("4. 결과 다운로드")
    download_row = {
        "행정동코드": row["행정동코드"],
        "시군구": row["시군구"],
        "행정동": row["행정동"],
        "위험유형": row["위험유형"],
        "우선순위등급": row["우선순위등급"],
        "정책우선기준": criterion,
        "정책적용강도_pct": intensity_percent,
        "선택정책": " / ".join(selected_policies),
        "적용전_DLFI": combined["before_dlfi"],
        "적용후_DLFI": combined["after_dlfi"],
        "DLFI_감소": combined["reduction"],
        "DLFI_감소율_pct": combined["reduction_rate"],
        "추천패키지": " → ".join(package),
        "정책효과_구분": "초기 규칙 기반 상대적 What-if",
    }
    download_df = pd.DataFrame([download_row])
    st.download_button(
        "시뮬레이션 결과 CSV 다운로드",
        data=download_df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"policy_whatif_{row['행정동']}.csv",
        mime="text/csv",
        use_container_width=True,
        key="feature3_download",
    )

    st.caption(
        "정책효과는 실증 결과가 아니라 정책별 영향 규칙을 적용한 상대적 What-if 분석입니다. "
        "실제 도입 전 현장조사·시범운영·관계기관 협의를 통해 효과값을 보정해야 합니다."
    )


# -----------------------------------------------------------------------------
# 6. 단독 실행 진입점
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    st.set_page_config(
        page_title="정책 What-if 시뮬레이터",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    render_policy_simulator()
