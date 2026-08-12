"""D-Curb Guardian 기능 2 공모전 시연용 Streamlit 화면.

실행
    pip install streamlit pandas altair plotly pydeck
    streamlit run D_Curb_Guardian_Feature2_Streamlit.py

필수 파일
    dcurb_config.py
    risk_type_master.csv
    risk_type_rules.csv

선택 파일
    daejeon_admin_dong.geojson
    reliability_master.csv
    loading_zone_candidates.csv

주의
    이 화면은 1차 MVP의 6개 지표 기반 위험유형 분류 화면입니다.
    날씨·행사·공사 시나리오와 정책 효과 What-if는 기능 2에서 계산하지 않습니다.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from dcurb_config import (
    DRIVER_POLICY_TEXT_CSV,
    DRIVER_TIMEBAND_CSV,
    FEATURE2_DIR,
    FINAL_DATA_DIR,
    FLEXIBLE_PARKING_DASHBOARD_CSV,
    FLEXIBLE_PARKING_JOIN_CSV,
    LOGISTICS_TIMEBAND_CSV,
    RISK_TYPE_MASTER_CSV,
    RISK_TYPE_RULES_CSV,
)


TYPE_ORDER = [
    "배송수요 과밀형",
    "하역공간 부족형",
    "단속반복형",
    "보행충돌형",
    "교통방해형",
    "안전취약형",
    "복합위험형",
]

RISK_COLUMNS = {
    "배송수요": "배송수요위험점수",
    "하역공간 부족": "하역공간부족위험점수",
    "단속반복": "단속반복위험점수",
    "보행충돌": "보행충돌위험점수",
    "교통방해": "교통방해위험점수",
    "안전취약": "안전취약위험점수",
}

FACTOR_POLICY = {
    "배송수요": [
        "배송물량 집중시간 분산",
        "공동배송 또는 권역별 배송 슬롯 검토",
    ],
    "하역공간 부족": [
        "임시 하역면과 공영주차장 유휴면 우선 검토",
        "마이크로 하역거점 후보지 기능으로 연결",
    ],
    "단속반복": [
        "상습구간 탄력 하역권과 허용시간 검토",
        "단속 안내표지와 현장 운영기준 정비",
    ],
    "보행충돌": [
        "보행 피크시간 하역 회피",
        "보행안전 완충구간과 진입 동선 검토",
    ],
    "교통방해": [
        "혼잡시간대 차로 점유 최소화",
        "교차로·버스정류장 인접 후보지 제외",
    ],
    "안전취약": [
        "등하교·취약계층 이동시간 하역 회피",
        "보호구역 반경 내 후보지 추천 제외",
    ],
}

REQUIRED_MASTER = [
    "행정동코드",
    "시군구",
    "행정동",
    "DLFI_순위",
    "DLFI",
    "고위험여부",
    "위험유형",
    "기본위험유형",
    "복합위험여부",
    "복합판정근거",
    "지역특성태그",
    "지역특성근거",
    "주요위험요인1",
    "주요위험요인2",
    "주요위험요인3",
    "주요위험점수1",
    "주요위험점수2",
    "주요위험점수3",
    "한줄자동해석",
    "권장정책",
    *RISK_COLUMNS.values(),
]


st.set_page_config(
    page_title="D-Curb Guardian · 위험유형",
    page_icon="◼",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --ink:#202020;
        --gray-1:#4b4b4b;
        --gray-2:#777777;
        --gray-3:#b9b9b9;
        --line:#dddddd;
        --paper:#ffffff;
        --wash:#f5f5f5;
    }
    .stApp {background:var(--paper); color:var(--ink);}
    [data-testid="stSidebar"] {
        background:#f3f3f3;
        border-right:1px solid var(--line);
    }
    [data-testid="stMetric"] {
        border:1px solid var(--line);
        background:#ffffff;
        border-radius:6px;
        padding:14px 16px;
        box-shadow:none;
    }
    [data-testid="stMetricLabel"] {color:var(--gray-2);}
    [data-testid="stMetricValue"] {color:var(--ink);}
    .dc-eyebrow {
        font-size:.76rem;
        letter-spacing:.13em;
        color:var(--gray-2);
        margin-bottom:.2rem;
    }
    .dc-title {
        font-size:2rem;
        line-height:1.2;
        font-weight:750;
        color:var(--ink);
        margin:0 0 .35rem 0;
    }
    .dc-lead {
        color:var(--gray-2);
        margin:0 0 1.3rem 0;
    }
    .dc-badge {
        display:inline-block;
        border-radius:4px;
        padding:.35rem .62rem;
        background:var(--ink);
        color:#ffffff;
        font-size:.86rem;
        font-weight:650;
    }
    .dc-outline-badge {
        display:inline-block;
        border:1px solid var(--gray-1);
        border-radius:4px;
        padding:.3rem .55rem;
        color:var(--ink);
        font-size:.8rem;
        margin-left:.35rem;
    }
    .dc-panel {
        border:1px solid var(--line);
        background:#ffffff;
        border-radius:6px;
        padding:1rem 1.1rem;
        margin:.45rem 0;
    }
    .dc-panel strong {color:var(--ink);}
    .dc-policy {
        border-left:4px solid var(--ink);
        background:var(--wash);
        padding:.9rem 1rem;
        margin:.65rem 0;
    }
    .dc-card {
        border:1px solid var(--line);
        border-radius:6px;
        padding:1rem;
        min-height:175px;
        background:#ffffff;
    }
    .dc-card h4 {margin:0 0 .55rem 0; color:var(--ink);}
    .dc-card p {color:var(--gray-2); margin:.25rem 0;}
    .stTabs [data-baseweb="tab-list"] {
        gap:.8rem;
        border-bottom:1px solid var(--line);
    }
    .stTabs [aria-selected="true"] {
        color:var(--ink);
        font-weight:700;
    }
    .stButton > button, .stDownloadButton > button {
        border-radius:4px;
        border:1px solid var(--gray-1);
        box-shadow:none;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def candidate_paths(filename: str, configured_path: Path | None = None) -> list[Path]:
    paths: list[Path] = []
    if configured_path is not None:
        paths.append(configured_path)
    paths.extend(
        [
            APP_DIR / filename,
            APP_DIR / "input_data" / filename,
            FEATURE2_DIR / filename,
            FINAL_DATA_DIR / filename,
        ]
    )
    # 동일 경로 중복 제거
    return list(dict.fromkeys(paths))


def find_file(filename: str, configured_path: Path | None = None) -> Path | None:
    return next(
        (
            path
            for path in candidate_paths(filename, configured_path)
            if path.exists()
        ),
        None,
    )


def read_csv_auto(file_or_path) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "cp949"):
        try:
            if hasattr(file_or_path, "seek"):
                file_or_path.seek(0)
            return pd.read_csv(
                file_or_path,
                encoding=encoding,
                dtype={"행정동코드": "string"},
            )
        except UnicodeDecodeError as error:
            last_error = error
    raise ValueError("CSV 인코딩을 확인할 수 없습니다.") from last_error


@st.cache_data(show_spinner=False)
def load_csv_path(path_text: str) -> pd.DataFrame:
    return read_csv_auto(Path(path_text))


@st.cache_data(show_spinner=False)
def load_json_path(path_text: str) -> dict:
    return json.loads(Path(path_text).read_text(encoding="utf-8"))


def load_required_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    master_path = find_file("risk_type_master.csv", RISK_TYPE_MASTER_CSV)
    rules_path = find_file("risk_type_rules.csv", RISK_TYPE_RULES_CSV)
    if master_path and rules_path:
        return load_csv_path(str(master_path)), load_csv_path(str(rules_path))

    st.sidebar.markdown("### 필수 데이터 연결")
    master_upload = st.sidebar.file_uploader(
        "risk_type_master.csv", type="csv", key="master_upload"
    )
    rules_upload = st.sidebar.file_uploader(
        "risk_type_rules.csv", type="csv", key="rules_upload"
    )
    if master_upload is None or rules_upload is None:
        st.info("필수 CSV 2개를 앱과 같은 폴더에 두거나 사이드바에서 업로드하세요.")
        st.stop()
    return read_csv_auto(master_upload), read_csv_auto(rules_upload)


def load_optional_csv(
    filename: str, configured_path: Path | None = None
) -> pd.DataFrame | None:
    path = find_file(filename, configured_path)
    return load_csv_path(str(path)) if path else None


def validate_master(master: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_MASTER if column not in master.columns]
    if missing:
        st.error(f"risk_type_master.csv 필수 컬럼 누락: {', '.join(missing)}")
        st.stop()

    numeric_columns = [
        "DLFI_순위",
        "DLFI",
        "고위험여부",
        "주요위험점수1",
        "주요위험점수2",
        "주요위험점수3",
        *RISK_COLUMNS.values(),
    ]
    for column in numeric_columns:
        master[column] = pd.to_numeric(master[column], errors="coerce")
    if master[numeric_columns].isna().any().any():
        st.error("위험유형 결과의 숫자 컬럼에 결측값이 있습니다.")
        st.stop()

    master["행정동코드"] = (
        master["행정동코드"].astype("string").str.replace(r"\.0$", "", regex=True)
    )
    master["지역명"] = master["시군구"].astype(str) + " " + master["행정동"].astype(str)
    return master.sort_values(["DLFI_순위", "지역명"], kind="stable").reset_index(
        drop=True
    )


def risk_frame(row: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "위험요인": list(RISK_COLUMNS),
            "표준화위험점수": [
                float(row[column]) for column in RISK_COLUMNS.values()
            ],
        }
    )


def radar_chart(row: pd.Series) -> go.Figure:
    labels = list(RISK_COLUMNS)
    values = [float(row[column]) for column in RISK_COLUMNS.values()]
    labels_closed = labels + [labels[0]]
    values_closed = values + [values[0]]
    figure = go.Figure(
        data=[
            go.Scatterpolar(
                r=values_closed,
                theta=labels_closed,
                fill="toself",
                fillcolor="rgba(60,60,60,0.16)",
                line=dict(color="#333333", width=2),
                marker=dict(color="#333333", size=5),
                hovertemplate="%{theta}: %{r:.1f}점<extra></extra>",
            )
        ]
    )
    figure.update_layout(
        height=385,
        margin=dict(l=45, r=45, t=30, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickvals=[20, 40, 60, 70, 80, 100],
                gridcolor="#dddddd",
                linecolor="#aaaaaa",
            ),
            angularaxis=dict(gridcolor="#e6e6e6", linecolor="#aaaaaa"),
        ),
        font=dict(color="#333333"),
    )
    return figure


def top_three_chart(row: pd.Series) -> alt.Chart:
    data = pd.DataFrame(
        {
            "순위": ["1순위", "2순위", "3순위"],
            "위험요인": [
                row["주요위험요인1"],
                row["주요위험요인2"],
                row["주요위험요인3"],
            ],
            "점수": [
                row["주요위험점수1"],
                row["주요위험점수2"],
                row["주요위험점수3"],
            ],
        }
    )
    return (
        alt.Chart(data)
        .mark_bar(color="#444444", cornerRadiusEnd=2)
        .encode(
            x=alt.X("점수:Q", scale=alt.Scale(domain=[0, 100]), title="표준화 위험점수"),
            y=alt.Y("위험요인:N", sort="-x", title=None),
            tooltip=["순위:N", "위험요인:N", alt.Tooltip("점수:Q", format=".1f")],
        )
        .properties(height=230)
        .configure_axis(
            gridColor="#e4e4e4",
            domainColor="#aaaaaa",
            tickColor="#aaaaaa",
            labelColor="#333333",
            titleColor="#555555",
        )
        .configure_view(strokeWidth=0)
    )


def similar_regions(master: pd.DataFrame, selected: pd.Series, count: int = 5) -> pd.DataFrame:
    candidates = master[
        (master["기본위험유형"] == selected["기본위험유형"])
        & (master["행정동코드"] != selected["행정동코드"])
    ].copy()
    if candidates.empty:
        return candidates
    vector = selected[list(RISK_COLUMNS.values())].astype(float).to_numpy()
    matrix = candidates[list(RISK_COLUMNS.values())].astype(float).to_numpy()
    candidates["지표거리"] = np.sqrt(((matrix - vector) ** 2).mean(axis=1)).round(1)
    return candidates.sort_values(
        ["지표거리", "DLFI_순위"], kind="stable"
    ).head(count)


def policies_for_row(row: pd.Series) -> list[str]:
    factors = [
        row["주요위험요인1"],
        row["주요위험요인2"],
        row["주요위험요인3"],
    ]
    use_factors = factors if row["복합위험여부"] == "예" else factors[:1]
    policies: list[str] = []
    for factor in use_factors:
        for policy in FACTOR_POLICY.get(factor, []):
            if policy not in policies:
                policies.append(policy)
    return policies


def comparison_chart(row_a: pd.Series, row_b: pd.Series) -> alt.Chart:
    rows: list[dict] = []
    for label, column in RISK_COLUMNS.items():
        rows.extend(
            [
                {"위험요인": label, "지역": row_a["지역명"], "점수": row_a[column]},
                {"위험요인": label, "지역": row_b["지역명"], "점수": row_b[column]},
            ]
        )
    data = pd.DataFrame(rows)
    return (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X("점수:Q", scale=alt.Scale(domain=[0, 100]), title="표준화 위험점수"),
            y=alt.Y("위험요인:N", sort=list(RISK_COLUMNS), title=None),
            yOffset="지역:N",
            color=alt.Color(
                "지역:N",
                scale=alt.Scale(range=["#333333", "#a9a9a9"]),
                legend=alt.Legend(title=None, orient="top"),
            ),
            tooltip=["지역:N", "위험요인:N", alt.Tooltip("점수:Q", format=".1f")],
        )
        .properties(height=330)
        .configure_axis(
            gridColor="#e4e4e4",
            domainColor="#aaaaaa",
            tickColor="#aaaaaa",
            labelColor="#333333",
            titleColor="#555555",
        )
        .configure_view(strokeWidth=0)
    )


def timeband_chart(
    rows: pd.DataFrame,
    value_columns: list[str],
    labels: dict[str, str],
) -> alt.Chart:
    plot = rows[["시간대", *value_columns]].melt(
        id_vars="시간대",
        var_name="지표",
        value_name="점수",
    )
    plot["지표"] = plot["지표"].map(labels)
    order = ["07~10", "10~12", "12~14", "14~17", "17~20", "20~23"]
    return (
        alt.Chart(plot)
        .mark_bar()
        .encode(
            x=alt.X("시간대:N", sort=order, title="시간대"),
            xOffset="지표:N",
            y=alt.Y("점수:Q", title="점수"),
            color=alt.Color(
                "지표:N",
                scale=alt.Scale(range=["#333333", "#aaaaaa"]),
                legend=alt.Legend(title=None, orient="top"),
            ),
            tooltip=["시간대:N", "지표:N", alt.Tooltip("점수:Q", format=".2f")],
        )
        .properties(height=330)
        .configure_axis(
            gridColor="#e4e4e4",
            domainColor="#aaaaaa",
            tickColor="#aaaaaa",
            labelColor="#333333",
            titleColor="#555555",
        )
        .configure_view(strokeWidth=0)
    )


def detect_property(properties: dict, candidates: list[str]) -> str | None:
    lowered = {str(key).lower(): key for key in properties}
    for candidate in candidates:
        if candidate in properties:
            return candidate
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return None


def prepare_map_geojson(
    source_geojson: dict, master: pd.DataFrame
) -> tuple[dict, int, int]:
    geojson = copy.deepcopy(source_geojson)
    features = geojson.get("features", [])
    if not features:
        raise ValueError("GeoJSON에 features가 없습니다.")

    properties = features[0].get("properties", {})
    code_key = detect_property(
        properties,
        ["행정동코드", "adm_cd", "ADM_CD", "emd_cd", "EMD_CD", "dong_code"],
    )
    name_key = detect_property(
        properties,
        ["행정동", "adm_nm", "ADM_NM", "emd_kor_nm", "EMD_KOR_NM", "dong_name"],
    )
    district_key = detect_property(
        properties,
        ["시군구", "sigungu", "SIG_KOR_NM", "sgg_nm", "district"],
    )
    if code_key is None and name_key is None:
        raise ValueError("GeoJSON 속성에 행정동코드 또는 행정동명이 필요합니다.")

    by_code = {
        str(row["행정동코드"]).replace(".0", ""): row
        for _, row in master.iterrows()
    }
    by_region = {row["지역명"]: row for _, row in master.iterrows()}
    by_name = {str(row["행정동"]): row for _, row in master.iterrows()}

    matched = 0
    for feature in features:
        props = feature.setdefault("properties", {})
        row = None
        if code_key and props.get(code_key) is not None:
            row = by_code.get(str(props[code_key]).replace(".0", ""))
        if row is None and name_key:
            dong_name = str(props.get(name_key, "")).strip()
            if district_key:
                row = by_region.get(f"{props.get(district_key, '')} {dong_name}".strip())
            if row is None:
                row = by_name.get(dong_name)

        if row is None:
            props.update(
                {
                    "지도행정동": str(props.get(name_key, "미매칭")),
                    "DLFI": None,
                    "위험유형": "데이터 미매칭",
                    "fill_color": [225, 225, 225, 80],
                    "line_color": [180, 180, 180, 180],
                }
            )
            continue

        matched += 1
        risk_ratio = 1 - ((float(row["DLFI_순위"]) - 1) / max(len(master) - 1, 1))
        gray = int(225 - risk_ratio * 175)
        props.update(
            {
                "지도행정동": row["지역명"],
                "DLFI": round(float(row["DLFI"]), 2),
                "위험유형": row["위험유형"],
                "주요원인": (
                    f"{row['주요위험요인1']} · "
                    f"{row['주요위험요인2']} · "
                    f"{row['주요위험요인3']}"
                ),
                "fill_color": [gray, gray, gray, 190],
                "line_color": [255, 255, 255, 220],
            }
        )
    return geojson, matched, len(features)


def render_map(geojson: dict) -> None:
    layer = pdk.Layer(
        "GeoJsonLayer",
        geojson,
        pickable=True,
        stroked=True,
        filled=True,
        get_fill_color="properties.fill_color",
        get_line_color="properties.line_color",
        line_width_min_pixels=1,
    )
    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=pdk.ViewState(
            latitude=36.3504,
            longitude=127.3845,
            zoom=9.6,
            pitch=0,
        ),
        map_style=None,
        tooltip={
            "html": (
                "<b>{지도행정동}</b><br/>"
                "DLFI: {DLFI}<br/>"
                "위험유형: {위험유형}<br/>"
                "TOP 3: {주요원인}"
            ),
            "style": {"backgroundColor": "#222222", "color": "#ffffff"},
        },
    )
    st.pydeck_chart(deck, width="stretch")


master_raw, rules = load_required_data()
master = validate_master(master_raw)
reliability = load_optional_csv("reliability_master.csv")
loading_candidates = load_optional_csv("loading_zone_candidates.csv")
logistics_timeband = load_optional_csv(
    "logistics_view_timeband_v3.csv", LOGISTICS_TIMEBAND_CSV
)
driver_timeband = load_optional_csv(
    "driver_view_timeband_v3.csv", DRIVER_TIMEBAND_CSV
)
driver_policy_text = load_optional_csv(
    "driver_facing_policy_text.csv", DRIVER_POLICY_TEXT_CSV
)
flexible_parking_dashboard = load_optional_csv(
    "DLFI_탄력주정차_82동_대시보드용_v2.csv",
    FLEXIBLE_PARKING_DASHBOARD_CSV,
)
flexible_parking_join = load_optional_csv(
    "탄력주정차_행정동매핑_DLFI조인_v2.csv",
    FLEXIBLE_PARKING_JOIN_CSV,
)
geojson_path = find_file("daejeon_admin_dong.geojson")
geojson_data = load_json_path(str(geojson_path)) if geojson_path else None

st.markdown('<div class="dc-eyebrow">D-CURB GUARDIAN · FEATURE 2</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="dc-title">행정동 위험유형 자동 분류</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="dc-lead">'
    "DLFI의 6개 위험요인을 표준화해 지역이 왜 위험한지 설명하고, "
    "유형별 정책 검토 방향으로 연결합니다."
    "</div>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### 사용자 화면")
    user_view = st.radio(
        "조회 목적",
        ["지자체 담당자", "물류기업 운영자", "배송기사", "팀 기능 연결"],
        label_visibility="collapsed",
    )
    st.markdown("### 조회 조건")
    district = st.selectbox(
        "시군구",
        ["전체"] + sorted(master["시군구"].dropna().astype(str).unique()),
    )
    type_filter = st.selectbox(
        "위험유형",
        ["전체"] + [
            type_name
            for type_name in TYPE_ORDER
            if type_name in master["기본위험유형"].values
        ],
    )

filtered = master.copy()
if district != "전체":
    filtered = filtered[filtered["시군구"] == district]
if type_filter != "전체":
    filtered = filtered[filtered["기본위험유형"] == type_filter]
if filtered.empty:
    st.warning("선택 조건에 해당하는 행정동이 없습니다.")
    st.stop()

with st.sidebar:
    selected_region = st.selectbox("행정동", filtered["지역명"].tolist())
    st.markdown("---")
    st.caption("표준화 점수는 82개 행정동 내 위험방향 백분위입니다.")
    st.caption("K-Means 결과는 최종 유형 판정에 사용하지 않습니다.")

selected = master.loc[master["지역명"] == selected_region].iloc[0]

if user_view == "지자체 담당자":
    badge_tail = (
        '<span class="dc-outline-badge">복합위험</span>'
        if selected["복합위험여부"] == "예"
        else ""
    )
    st.markdown(
        f'<span class="dc-badge">{selected["위험유형"]}</span>{badge_tail}',
        unsafe_allow_html=True,
    )
    st.subheader(selected["지역명"])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("DLFI", f'{selected["DLFI"]:.2f}')
    m2.metric("대전 순위", f'{int(selected["DLFI_순위"])}위')
    m3.metric("TOP 1 위험점수", f'{selected["주요위험점수1"]:.1f}')
    m4.metric("지역특성 태그", selected["지역특성태그"])

    st.markdown(
        f'<div class="dc-panel"><strong>한 줄 자동 해석</strong><br>'
        f'{selected["한줄자동해석"]}</div>',
        unsafe_allow_html=True,
    )

    tab_detail, tab_map, tab_policy, tab_compare, tab_evidence = st.tabs(
        ["위험 상세", "위험지도", "정책 추천", "지역 비교", "분류 근거"]
    )

    with tab_detail:
        left, right = st.columns([1.2, 1])
        with left:
            st.markdown("#### 6개 세부 지표")
            st.plotly_chart(
                radar_chart(selected),
                width="stretch",
                config={"displayModeBar": False},
            )
        with right:
            st.markdown("#### 주요 위험원인 TOP 3")
            st.altair_chart(top_three_chart(selected), width="stretch")
            st.caption(selected["복합판정근거"])

        st.markdown("#### 유사 유형 지역")
        similar = similar_regions(master, selected)
        if similar.empty:
            st.info("같은 기본 위험유형의 비교 지역이 없습니다.")
        else:
            st.dataframe(
                similar[
                    [
                        "DLFI_순위",
                        "시군구",
                        "행정동",
                        "DLFI",
                        "위험유형",
                        "지표거리",
                    ]
                ],
                hide_index=True,
                width="stretch",
            )

        st.markdown("#### 행정동 분류 결과")
        st.dataframe(
            filtered[
                [
                    "DLFI_순위",
                    "시군구",
                    "행정동",
                    "DLFI",
                    "위험유형",
                    "주요위험요인1",
                    "주요위험요인2",
                    "주요위험요인3",
                ]
            ],
            hide_index=True,
            width="stretch",
            height=300,
        )

    with tab_map:
        st.markdown("#### 행정동별 DLFI 위험지도")
        st.caption("DLFI 순위가 높을수록 진한 회색으로 표시합니다.")
        if geojson_data is None:
            uploaded_geojson = st.file_uploader(
                "대전 행정동 경계 GeoJSON 업로드",
                type=["geojson", "json"],
                key="geojson_upload",
            )
            if uploaded_geojson is not None:
                geojson_data = json.load(uploaded_geojson)
        if geojson_data is None:
            st.info(
                "`daejeon_admin_dong.geojson`을 앱 폴더에 추가하면 "
                "행정동코드 또는 행정동명으로 자동 연결됩니다."
            )
        else:
            try:
                map_geojson, matched, total = prepare_map_geojson(geojson_data, master)
                render_map(map_geojson)
                st.caption(f"GeoJSON 매칭: {matched}/{total}개 경계")
            except ValueError as error:
                st.error(str(error))

    with tab_policy:
        st.markdown(f"#### {selected['지역명']} 우선 검토 정책")
        policies = policies_for_row(selected)
        for order, policy in enumerate(policies, 1):
            st.markdown(
                f'<div class="dc-policy"><strong>{order}순위</strong> · {policy}</div>',
                unsafe_allow_html=True,
            )
        st.caption(
            "정책 추천은 위험유형과 TOP 3 요인을 연결한 규칙 기반 검토안이며, "
            "정책 효과를 확정적으로 예측한 값이 아닙니다."
        )

    with tab_compare:
        regions = master["지역명"].tolist()
        compare_default = 1 if len(regions) > 1 else 0
        left, right = st.columns(2)
        with left:
            region_a = st.selectbox("비교지역 A", regions, index=0, key="region_a")
        with right:
            region_b = st.selectbox(
                "비교지역 B", regions, index=compare_default, key="region_b"
            )
        row_a = master.loc[master["지역명"] == region_a].iloc[0]
        row_b = master.loc[master["지역명"] == region_b].iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric(region_a, f'DLFI {row_a["DLFI"]:.2f}', row_a["위험유형"], delta_color="off")
        c2.metric(region_b, f'DLFI {row_b["DLFI"]:.2f}', row_b["위험유형"], delta_color="off")
        c3.metric("DLFI 차이", f'{abs(row_a["DLFI"] - row_b["DLFI"]):.2f}')
        st.altair_chart(comparison_chart(row_a, row_b), width="stretch")

    with tab_evidence:
        st.markdown("#### 최종 분류 근거")
        evidence = pd.DataFrame(
            {
                "순위": ["TOP 1", "TOP 2", "TOP 3"],
                "위험요인": [
                    selected["주요위험요인1"],
                    selected["주요위험요인2"],
                    selected["주요위험요인3"],
                ],
                "표준화 위험점수": [
                    selected["주요위험점수1"],
                    selected["주요위험점수2"],
                    selected["주요위험점수3"],
                ],
            }
        )
        st.dataframe(evidence, hide_index=True, width="stretch")
        st.markdown(
            f"""
            <div class="dc-panel">
                <strong>복합위험 판정</strong><br>{selected["복합판정근거"]}<br><br>
                <strong>지역특성 결합</strong><br>{selected["지역특성근거"]}<br><br>
                <strong>K-Means 보조 결과</strong><br>
                군집 {selected.get("기존KMeans군집_보조", "")} ·
                {selected.get("기존KMeans유형_보조", "")}
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            "공동주택·상권·역세권 태그는 세대 비중·상가 수·승하차 지표가 "
            "실제로 연결되고 기준을 충족할 때만 표시합니다."
        )
        with st.expander("전체 위험유형 분류 규칙"):
            st.dataframe(rules, hide_index=True, width="stretch")

elif user_view == "물류기업 운영자":
    st.markdown(f'<span class="dc-badge">{selected["위험유형"]}</span>', unsafe_allow_html=True)
    st.subheader(f"{selected['지역명']} 운영 참고")
    selected_logistics = None
    if logistics_timeband is not None:
        logistics_timeband["행정동코드"] = (
            logistics_timeband["행정동코드"]
            .astype("string")
            .str.replace(r"\.0$", "", regex=True)
        )
        selected_logistics = logistics_timeband[
            logistics_timeband["행정동코드"] == str(selected["행정동코드"])
        ].copy()

    if selected_logistics is None or selected_logistics.empty:
        m1, m2, m3 = st.columns(3)
        m1.metric("DLFI", f'{selected["DLFI"]:.2f}')
        m2.metric("최우선 위험요인", selected["주요위험요인1"])
        m3.metric("복합위험 여부", selected["복합위험여부"])
        st.info(
            "`logistics_view_timeband_v3.csv`를 연결하면 6개 시간대별 "
            "혼잡도와 배송집중도를 표시합니다."
        )
    else:
        selected_logistics["동내_혼잡도순위"] = pd.to_numeric(
            selected_logistics["동내_혼잡도순위"], errors="coerce"
        )
        selected_logistics = selected_logistics.sort_values(
            ["동내_혼잡도순위", "시간대"], kind="stable"
        )
        low_congestion = selected_logistics.iloc[0]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("DLFI", f'{selected["DLFI"]:.2f}')
        m2.metric("혼잡이 낮은 시간대", low_congestion["시간대"])
        m3.metric("시간대 혼잡도", f'{float(low_congestion["혼잡도_시간대"]):.1f}')
        m4.metric("데이터 수단 수", int(low_congestion["데이터수단수"]))

        st.markdown("#### 시간대별 혼잡·배송집중")
        st.altair_chart(
            timeband_chart(
                selected_logistics,
                ["혼잡도_시간대", "배송집중도_시간대"],
                {
                    "혼잡도_시간대": "혼잡도",
                    "배송집중도_시간대": "배송집중도",
                },
            ),
            width="stretch",
        )
        st.dataframe(
            selected_logistics[
                [
                    "동내_혼잡도순위",
                    "시간대",
                    "혼잡도_시간대",
                    "배송집중도_시간대",
                    "도로혼잡도_시간대",
                    "버스혼잡도_시간대",
                    "지하철혼잡도_시간대",
                    "데이터수단수",
                ]
            ],
            hide_index=True,
            width="stretch",
        )

    st.markdown("#### 위험유형 기반 운영 검토사항")
    for policy in policies_for_row(selected):
        st.markdown(f"- {policy}")
    st.caption(
        "시간대 데이터는 물류기업 운영 참고 화면에만 사용하며, "
        "행정동 위험유형은 final_modelling.csv의 6개 DLFI 지표로 계산합니다."
    )

elif user_view == "배송기사":
    st.markdown(f'<span class="dc-badge">{selected["위험유형"]}</span>', unsafe_allow_html=True)
    st.subheader(f"{selected['지역명']} 배송 주의")
    selected_driver = None
    if driver_timeband is not None:
        driver_timeband["행정동코드"] = (
            driver_timeband["행정동코드"]
            .astype("string")
            .str.replace(r"\.0$", "", regex=True)
        )
        selected_driver = driver_timeband[
            driver_timeband["행정동코드"] == str(selected["행정동코드"])
        ].copy()

    if selected_driver is None or selected_driver.empty:
        st.markdown(
            f'<div class="dc-panel"><strong>현재 지역 핵심 위험</strong><br>'
            f'{selected["주요위험요인1"]} {selected["주요위험점수1"]:.1f}점 · '
            f'{selected["주요위험요인2"]} {selected["주요위험점수2"]:.1f}점 · '
            f'{selected["주요위험요인3"]} {selected["주요위험점수3"]:.1f}점</div>',
            unsafe_allow_html=True,
        )
        st.info(
            "`driver_view_timeband_v3.csv`를 연결하면 추천·보통·회피 시간대와 "
            "실측검증 결과를 표시합니다."
        )
    else:
        selected_driver["동내_시간대순위"] = pd.to_numeric(
            selected_driver["동내_시간대순위"], errors="coerce"
        )
        selected_driver = selected_driver.sort_values(
            ["동내_시간대순위", "시간대"], kind="stable"
        )
        best_time = selected_driver.iloc[0]

        guide = ""
        if driver_policy_text is not None:
            mapping = driver_policy_text.drop_duplicates(
                "원본_추천정책_텍스트", keep="first"
            ).set_index("원본_추천정책_텍스트")["기사용_안내문구"]
            guide = mapping.get(best_time["추천정책_텍스트"], "")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("추천 시간대", best_time["시간대"])
        m2.metric("하역 등급", best_time["탄력하역권_등급_표시"])
        m3.metric("시간대 순위", f'{int(best_time["동내_시간대순위"])}위')
        m4.metric("실측검증", best_time["모델실측_검증플래그"])

        if guide:
            st.markdown(
                f'<div class="dc-policy"><strong>기사 안내</strong><br>{guide}</div>',
                unsafe_allow_html=True,
            )

        st.markdown("#### 시간대별 하역 안내")
        st.dataframe(
            selected_driver[
                [
                    "동내_시간대순위",
                    "시간대",
                    "탄력하역권_등급_표시",
                    "혼잡도_시간대",
                    "배송집중도_시간대",
                    "하역추천점수_시간대",
                    "순위신뢰여부",
                    "모델실측_검증플래그",
                ]
            ],
            hide_index=True,
            width="stretch",
        )
        mismatch_count = int(
            (selected_driver["모델실측_검증플래그"] != "일치").sum()
        )
        if mismatch_count:
            st.warning(
                f"6개 시간대 중 {mismatch_count}개는 모델과 실측 검증 결과가 "
                "일치하지 않아 현장 확인이 필요합니다."
            )

    st.markdown("#### 위험유형 기반 현장 주의")
    for policy in policies_for_row(selected)[:4]:
        st.markdown(f"- {policy}")
    st.caption(
        "위험유형은 final_modelling.csv 기반 행정동 분석이며, "
        "시간대 등급은 driver_view_timeband_v3의 운영 참고정보입니다. "
        "현장 통제·표지·안전요원의 안내를 우선합니다."
    )

else:
    st.subheader("팀 기능 연결")
    card_1, card_2, card_3 = st.columns(3)
    with card_1:
        st.markdown(
            """
            <div class="dc-card">
                <h4>① 하역공간 후보지·운영시간</h4>
                <p>기능 2가 제공하는 행정동·위험유형·TOP 3를 전달합니다.</p>
                <p>하역공간 부족형과 복합위험형을 우선 후보지 탐색 대상으로 사용합니다.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with card_2:
        st.markdown(
            """
            <div class="dc-card">
                <h4>③ 정책 What-if·패키지</h4>
                <p>기능 2의 위험유형과 정책 검토안을 시뮬레이터 입력으로 전달합니다.</p>
                <p>효과 계산은 기능 3에서 수행하며 기능 2가 임의 예측하지 않습니다.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with card_3:
        st.markdown(
            """
            <div class="dc-card">
                <h4>④ 데이터 신뢰도 레이어</h4>
                <p>행정동코드로 신뢰도·품질 플래그를 결합합니다.</p>
                <p>위험유형과 데이터 한계를 같은 상세 화면에서 확인합니다.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("#### 화면 간 전달값")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "전달 항목": "행정동 식별",
                    "컬럼": "행정동코드·시군구·행정동",
                    "사용 기능": "1·3·4 공통",
                },
                {
                    "전달 항목": "대표 분류",
                    "컬럼": "위험유형·기본위험유형·복합위험여부",
                    "사용 기능": "후보지 우선순위·정책 패키지",
                },
                {
                    "전달 항목": "설명 근거",
                    "컬럼": "주요위험요인1~3·주요위험점수1~3",
                    "사용 기능": "정책 근거·현장 안내",
                },
                {
                    "전달 항목": "정책 검토안",
                    "컬럼": "권장정책",
                    "사용 기능": "기능 3 초기 정책 선택",
                },
            ]
        ),
        hide_index=True,
        width="stretch",
    )

    st.markdown("#### 확인한 팀 통합 파일")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "파일": "final_modelling.csv",
                    "크기": "82행",
                    "기능 2 사용": "공식 분류 입력",
                },
                {
                    "파일": "logistics_view_timeband_v3.csv",
                    "크기": "492행(82동×6시간대)",
                    "기능 2 사용": "물류기업 화면 연결",
                },
                {
                    "파일": "driver_view_timeband_v3.csv",
                    "크기": "492행(82동×6시간대)",
                    "기능 2 사용": "배송기사 화면·실측검증 연결",
                },
                {
                    "파일": "driver_facing_policy_text.csv",
                    "크기": "11개 정책문구",
                    "기능 2 사용": "배송기사 안내문구 변환",
                },
                {
                    "파일": "DLFI_탄력주정차_82동_대시보드용_v2.csv",
                    "크기": "82행",
                    "기능 2 사용": "기능 1 연결",
                },
                {
                    "파일": "탄력주정차_행정동매핑_DLFI조인_v2.csv",
                    "크기": "55구간·15개 행정동",
                    "기능 2 사용": "기능 1 현행 지정구간 연결",
                },
            ]
        ),
        hide_index=True,
        width="stretch",
    )

    if loading_candidates is not None:
        with st.expander("기능 1 후보지 데이터 미리보기"):
            st.dataframe(loading_candidates, hide_index=True, width="stretch")
    if reliability is not None:
        with st.expander("기능 4 신뢰도 데이터 미리보기"):
            st.dataframe(reliability, hide_index=True, width="stretch")
    if flexible_parking_dashboard is not None:
        with st.expander("기능 1 탄력주정차 82동 데이터 미리보기"):
            st.dataframe(
                flexible_parking_dashboard, hide_index=True, width="stretch"
            )
    if flexible_parking_join is not None:
        with st.expander("기능 1 기존 지정구간 조인 데이터 미리보기"):
            st.dataframe(flexible_parking_join, hide_index=True, width="stretch")
