"""
D-Curb Guardian 공모전 시연용 Streamlit 서비스

구현 화면
1. 행정동 선택 및 위험유형 필터
2. DLFI·위험유형 상세 카드
3. 6개 지표 비교 그래프
4. 행정동 경계 GeoJSON 기반 위험지도
5. 위험유형 기반 정책 추천
6. 두 지역 위험도 비교
7. 하역공간 후보지 기능 연결
8. 정책 What-if 시뮬레이터 연결
9. 데이터 신뢰도·품질관리 레이어 연결

실행 명령
    pip install -r requirements.txt
    streamlit run D_Curb_Guardian_Streamlit.py
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st


APP_DIR = Path(__file__).resolve().parent

FILE_NAMES = {
    "master": "risk_type_master.csv",
    "rules": "risk_type_rules.csv",
    "reliability": "reliability_master.csv",
    "registry": "data_source_registry.csv",
    "loading": "loading_zone_candidates.csv",
    "geojson": "daejeon_admin_dong.geojson",
}

TYPE_ORDER = [
    "공동주택 배송집중형",
    "상권·교통 혼잡형",
    "역세권 보행충돌형",
    "단속반복형",
    "안전취약형",
    "하역공간 부족형",
]

RISK_COLUMNS = {
    "배송수요": "배송수요위험백분위",
    "교통방해": "교통방해위험백분위",
    "보행충돌": "보행충돌위험백분위",
    "단속반복": "단속반복위험백분위",
    "안전취약": "안전취약위험백분위",
    "하역부족": "하역부족위험백분위",
}

POLICY_PACKAGES = {
    "공동주택 배송집중형": [
        "공동주택 배송시간 슬롯 분산",
        "단지별 공동배송 운영 검토",
        "17~20시 집중물량 분산 유도",
    ],
    "상권·교통 혼잡형": [
        "상권 혼잡시간대 하역 회피",
        "단시간 탄력 하역구역 운영",
        "버스정류장·교차로 인접구간 제외",
    ],
    "역세권 보행충돌형": [
        "출퇴근 보행 피크시간 하역 제한",
        "역 출입구 주변 완충구간 설정",
        "보행량이 낮은 시간대로 배송 전환",
    ],
    "단속반복형": [
        "상습단속구간 탄력 하역권 검토",
        "단속 CCTV·안내표지 위치 재검토",
        "허용시간과 금지시간을 현장에 명확히 표시",
    ],
    "안전취약형": [
        "등하교시간 하역 회피",
        "보호구역 반경 내 후보지 추천 제외",
        "취약계층 이동시간 장기정차 최소화",
    ],
    "하역공간 부족형": [
        "임시 하역면 우선 설치",
        "공영주차장·공공시설 유휴공간 검토",
        "소형 마이크로 물류거점 후보지 조사",
    ],
}

REQUIRED_MASTER = [
    "행정동코드",
    "시군구",
    "행정동",
    "DLFI_순위",
    "DLFI",
    "고위험여부",
    "주위험유형",
    "보조위험유형",
    "주요근거지표",
    "보조근거지표",
    "주요원점수",
    "보조원점수",
    "주요위험백분위",
    "보조위험백분위",
    "분류명확도",
    "권장관리방향",
    *RISK_COLUMNS.values(),
]


st.set_page_config(
    page_title="D-Curb Guardian",
    page_icon="◼",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --charcoal:#262626;
        --dark:#595959;
        --mid:#a6a6a6;
        --line:#d9d9d9;
        --soft:#f2f2f2;
        --white:#ffffff;
    }
    [data-testid="stSidebar"] {
        background:#f5f5f5;
        border-right:1px solid var(--line);
    }
    [data-testid="stMetric"] {
        background:var(--white);
        border:1px solid var(--line);
        border-radius:4px;
        padding:14px 16px;
        box-shadow:none;
    }
    [data-testid="stMetricLabel"] {color:#666666;}
    [data-testid="stMetricValue"] {color:var(--charcoal);}
    .dc-label {
        color:#707070;
        font-size:.8rem;
        letter-spacing:.08em;
        margin-bottom:.1rem;
    }
    .dc-title {
        color:var(--charcoal);
        font-size:2rem;
        font-weight:700;
        margin:0;
    }
    .dc-subtitle {
        color:#666666;
        margin:.3rem 0 1.2rem 0;
    }
    .dc-badge {
        display:inline-block;
        background:var(--charcoal);
        color:var(--white);
        border-radius:3px;
        padding:.28rem .55rem;
        font-size:.86rem;
        font-weight:600;
    }
    .dc-policy {
        border-left:4px solid var(--charcoal);
        background:var(--soft);
        padding:.9rem 1rem;
        margin:.6rem 0;
    }
    .dc-link-card {
        border:1px solid var(--line);
        border-radius:4px;
        padding:1rem;
        background:var(--white);
        min-height:150px;
    }
    .dc-link-card h4 {margin-top:0;color:var(--charcoal);}
    .stTabs [data-baseweb="tab-list"] {
        gap:1rem;
        border-bottom:1px solid var(--line);
    }
    .stTabs [aria-selected="true"] {
        color:var(--charcoal);
        font-weight:700;
    }
    .stButton > button, .stDownloadButton > button {
        border-radius:3px;
        border:1px solid var(--dark);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def find_file(filename: str) -> Path | None:
    for directory in (APP_DIR, APP_DIR.parent):
        candidate = directory / filename
        if candidate.exists():
            return candidate
    return None


def read_csv_auto(file_or_path) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "utf-8", "cp949"):
        try:
            if hasattr(file_or_path, "seek"):
                file_or_path.seek(0)
            return pd.read_csv(
                file_or_path,
                encoding=encoding,
                dtype={"행정동코드": "string"},
            )
        except UnicodeDecodeError:
            continue
    raise ValueError("CSV 인코딩을 확인할 수 없습니다.")


@st.cache_data(show_spinner=False)
def load_csv_path(path_text: str) -> pd.DataFrame:
    return read_csv_auto(Path(path_text))


@st.cache_data(show_spinner=False)
def load_json_path(path_text: str) -> dict:
    return json.loads(Path(path_text).read_text(encoding="utf-8"))


def load_required_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    master_path = find_file(FILE_NAMES["master"])
    rules_path = find_file(FILE_NAMES["rules"])
    if master_path and rules_path:
        return load_csv_path(str(master_path)), load_csv_path(str(rules_path))

    st.sidebar.markdown("### 필수 데이터 연결")
    master_upload = st.sidebar.file_uploader(
        FILE_NAMES["master"], type="csv", key="master_upload"
    )
    rules_upload = st.sidebar.file_uploader(
        FILE_NAMES["rules"], type="csv", key="rules_upload"
    )
    if master_upload is None or rules_upload is None:
        st.info("위험유형 결과 CSV 2개를 앱 폴더에 두거나 사이드바에서 업로드하세요.")
        st.stop()
    return read_csv_auto(master_upload), read_csv_auto(rules_upload)


def validate_master(master: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_MASTER if column not in master.columns]
    if missing:
        st.error(f"risk_type_master.csv 필수 컬럼 누락: {', '.join(missing)}")
        st.stop()

    numeric_columns = [
        "DLFI_순위",
        "DLFI",
        "고위험여부",
        "주요원점수",
        "보조원점수",
        "주요위험백분위",
        "보조위험백분위",
        "분류명확도",
        *RISK_COLUMNS.values(),
    ]
    for column in numeric_columns:
        master[column] = pd.to_numeric(master[column], errors="coerce")
    master["행정동코드"] = master["행정동코드"].astype("string").str.replace(
        r"\.0$", "", regex=True
    )
    master["지역명"] = master["시군구"].astype(str) + " " + master["행정동"].astype(str)
    return master.sort_values(["DLFI_순위", "지역명"], kind="stable").reset_index(
        drop=True
    )


def load_optional_csv(key: str) -> pd.DataFrame | None:
    path = find_file(FILE_NAMES[key])
    return load_csv_path(str(path)) if path else None


def load_optional_geojson() -> dict | None:
    path = find_file(FILE_NAMES["geojson"])
    if path:
        return load_json_path(str(path))
    return None


def risk_frame(row: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "위험요인": list(RISK_COLUMNS),
            "위험백분위": [float(row[column]) for column in RISK_COLUMNS.values()],
        }
    )


def gray_bar_chart(data: pd.DataFrame, x: str, y: str, height: int = 280) -> alt.Chart:
    return (
        alt.Chart(data)
        .mark_bar(color="#4A4A4A", cornerRadiusEnd=2)
        .encode(
            x=alt.X(f"{x}:Q", title=x, scale=alt.Scale(domain=[0, 100])),
            y=alt.Y(f"{y}:N", title=None, sort="-x"),
            tooltip=[alt.Tooltip(f"{y}:N"), alt.Tooltip(f"{x}:Q", format=".1f")],
        )
        .properties(height=height)
        .configure_axis(
            gridColor="#E6E6E6",
            domainColor="#A6A6A6",
            tickColor="#A6A6A6",
            labelColor="#404040",
            titleColor="#404040",
        )
        .configure_view(strokeWidth=0)
    )


def comparison_chart(row_a: pd.Series, row_b: pd.Series) -> alt.Chart:
    rows = []
    for label, column in RISK_COLUMNS.items():
        rows.extend(
            [
                {
                    "위험요인": label,
                    "지역": row_a["지역명"],
                    "위험백분위": float(row_a[column]),
                },
                {
                    "위험요인": label,
                    "지역": row_b["지역명"],
                    "위험백분위": float(row_b[column]),
                },
            ]
        )
    data = pd.DataFrame(rows)
    return (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X(
                "위험백분위:Q",
                title="위험백분위",
                scale=alt.Scale(domain=[0, 100]),
            ),
            y=alt.Y("위험요인:N", title=None, sort=list(RISK_COLUMNS)),
            yOffset="지역:N",
            color=alt.Color(
                "지역:N",
                scale=alt.Scale(range=["#333333", "#A6A6A6"]),
                legend=alt.Legend(title=None, orient="top"),
            ),
            tooltip=["지역:N", "위험요인:N", alt.Tooltip("위험백분위:Q", format=".1f")],
        )
        .properties(height=330)
        .configure_axis(
            gridColor="#E6E6E6",
            domainColor="#A6A6A6",
            tickColor="#A6A6A6",
            labelColor="#404040",
            titleColor="#404040",
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

    first_properties = features[0].get("properties", {})
    code_key = detect_property(
        first_properties,
        ["행정동코드", "adm_cd", "ADM_CD", "emd_cd", "EMD_CD", "dong_code"],
    )
    name_key = detect_property(
        first_properties,
        ["행정동", "adm_nm", "ADM_NM", "emd_kor_nm", "EMD_KOR_NM", "dong_name"],
    )
    district_key = detect_property(
        first_properties,
        ["시군구", "sigungu", "SIG_KOR_NM", "sgg_nm", "district"],
    )
    if code_key is None and name_key is None:
        raise ValueError(
            "GeoJSON 속성에 행정동코드 또는 행정동명 컬럼이 필요합니다."
        )

    by_code = {
        str(row["행정동코드"]).replace(".0", ""): row
        for _, row in master.iterrows()
    }
    by_region = {row["지역명"]: row for _, row in master.iterrows()}
    by_name = {str(row["행정동"]): row for _, row in master.iterrows()}

    matched = 0
    for feature in features:
        properties = feature.setdefault("properties", {})
        row = None
        if code_key and properties.get(code_key) is not None:
            code = str(properties.get(code_key)).replace(".0", "")
            row = by_code.get(code)
        if row is None and name_key:
            dong_name = str(properties.get(name_key, "")).strip()
            if district_key:
                region = f"{properties.get(district_key, '')} {dong_name}".strip()
                row = by_region.get(region)
            if row is None:
                row = by_name.get(dong_name)

        if row is None:
            properties.update(
                {
                    "지도행정동": str(properties.get(name_key, "미매칭")),
                    "DLFI": None,
                    "주위험유형": "데이터 미매칭",
                    "fill_color": [225, 225, 225, 80],
                    "line_color": [180, 180, 180, 180],
                }
            )
            continue

        matched += 1
        risk_ratio = 1 - ((float(row["DLFI_순위"]) - 1) / max(len(master) - 1, 1))
        gray = int(225 - risk_ratio * 175)
        properties.update(
            {
                "지도행정동": row["지역명"],
                "DLFI": round(float(row["DLFI"]), 2),
                "주위험유형": row["주위험유형"],
                "보조위험유형": row["보조위험유형"],
                "권장관리방향": row["권장관리방향"],
                "fill_color": [gray, gray, gray, 185],
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
    view_state = pdk.ViewState(
        latitude=36.3504,
        longitude=127.3845,
        zoom=9.6,
        pitch=0,
    )
    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        map_style=None,
        tooltip={
            "html": (
                "<b>{지도행정동}</b><br/>"
                "DLFI: {DLFI}<br/>"
                "주위험유형: {주위험유형}<br/>"
                "보조위험유형: {보조위험유형}"
            ),
            "style": {
                "backgroundColor": "#262626",
                "color": "#ffffff",
            },
        },
    )
    st.pydeck_chart(deck, use_container_width=True)


def policy_priority(row: pd.Series) -> str:
    if int(row["고위험여부"]) == 1:
        return "시범사업 우선 검토"
    if float(row["DLFI_순위"]) <= len(master) * 0.4:
        return "중점 관리 검토"
    return "일반 모니터링"


def show_policy_package(row: pd.Series) -> None:
    primary = POLICY_PACKAGES.get(row["주위험유형"], [row["권장관리방향"]])
    secondary = POLICY_PACKAGES.get(row["보조위험유형"], [])
    st.markdown(
        f'<span class="dc-badge">{policy_priority(row)}</span>',
        unsafe_allow_html=True,
    )
    st.subheader(f'{row["지역명"]} 정책 패키지')
    left, right = st.columns(2)
    with left:
        st.markdown(f"#### 1순위 · {row['주위험유형']}")
        for item in primary:
            st.markdown(f"- {item}")
    with right:
        st.markdown(f"#### 보완 · {row['보조위험유형']}")
        for item in secondary[:2]:
            st.markdown(f"- {item}")
    st.markdown(
        f"""
        <div class="dc-policy">
            <strong>기본 권장 관리방향</strong><br>
            {row["권장관리방향"]}
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_what_if(row: pd.Series) -> None:
    st.markdown("#### 정책 What-if 시뮬레이터")
    st.caption("정책 효과를 확정하는 값이 아니라 공모전 데모용 가정 기반 예상치입니다.")
    left, right = st.columns(2)
    with left:
        loading_spaces = st.slider("추가 임시 하역면 수", 0, 10, 3)
    with right:
        dispersion = st.slider("배송 분산율", 0, 30, 15, format="%d%%")

    loading_rate = min(0.25, loading_spaces * 0.05)
    dispersion_rate = dispersion / 100
    overlap = min(loading_rate, dispersion_rate) * 0.4
    total_rate = min(0.45, loading_rate + dispersion_rate - overlap)
    base_dlfi = float(row["DLFI"])
    expected_dlfi = base_dlfi * (1 - total_rate)

    metric_1, metric_2, metric_3 = st.columns(3)
    metric_1.metric("적용 전 DLFI", f"{base_dlfi:.2f}")
    metric_2.metric("적용 후 예상 DLFI", f"{expected_dlfi:.2f}")
    metric_3.metric("예상 감소율", f"{total_rate * 100:.1f}%")
    st.progress(min(total_rate / 0.45, 1.0))
    st.caption(
        f"하역면 효과 {loading_rate * 100:.1f}% · "
        f"배송분산 효과 {dispersion_rate * 100:.1f}% · 중복효과 조정 적용"
    )


master_raw, rules = load_required_data()
master = validate_master(master_raw)
reliability = load_optional_csv("reliability")
registry = load_optional_csv("registry")
loading_candidates = load_optional_csv("loading")
geojson_data = load_optional_geojson()

st.markdown('<div class="dc-label">D-CURB GUARDIAN</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="dc-title">행정동 위험유형 자동 분류</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="dc-subtitle">'
    "지역별 위험 원인을 설명하고 정책 선정·효과 비교·데이터 신뢰도 확인까지 연결합니다."
    "</div>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### 조회 조건")
    district = st.selectbox(
        "시군구",
        ["전체"] + sorted(master["시군구"].dropna().astype(str).unique()),
    )
    risk_type = st.selectbox(
        "주위험유형",
        ["전체"] + [item for item in TYPE_ORDER if item in master["주위험유형"].values],
    )

filtered = master.copy()
if district != "전체":
    filtered = filtered[filtered["시군구"] == district]
if risk_type != "전체":
    filtered = filtered[filtered["주위험유형"] == risk_type]
if filtered.empty:
    st.warning("선택 조건에 해당하는 행정동이 없습니다.")
    st.stop()

with st.sidebar:
    selected_region = st.selectbox("행정동", filtered["지역명"].tolist())
    st.markdown("---")
    st.caption("분류명확도는 예측확률이 아닌 주·보조 위험의 상대적 차이입니다.")

selected = master.loc[master["지역명"] == selected_region].iloc[0]

(
    tab_dashboard,
    tab_map,
    tab_policy,
    tab_compare,
    tab_connection,
    tab_quality,
) = st.tabs(
    [
        "위험유형 분석",
        "위험지도",
        "정책 추천",
        "지역 비교",
        "팀 기능 연계",
        "데이터 신뢰도",
    ]
)

with tab_dashboard:
    st.markdown(
        f'<span class="dc-badge">{selected["주위험유형"]}</span>',
        unsafe_allow_html=True,
    )
    st.subheader(selected["지역명"])
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("DLFI", f'{selected["DLFI"]:.2f}')
    m2.metric("대전 순위", f'{int(selected["DLFI_순위"])}위')
    m3.metric("분류명확도", f'{selected["분류명확도"]:.1f}')
    m4.metric("보조위험유형", selected["보조위험유형"])

    left, right = st.columns([1.7, 1])
    with left:
        st.markdown("#### 6개 위험지표 비교")
        st.altair_chart(
            gray_bar_chart(risk_frame(selected), "위험백분위", "위험요인"),
            use_container_width=True,
        )
    with right:
        st.markdown("#### 자동 분류 근거")
        evidence = pd.DataFrame(
            {
                "구분": ["주요 위험", "보조 위험"],
                "지표": [selected["주요근거지표"], selected["보조근거지표"]],
                "원점수": [selected["주요원점수"], selected["보조원점수"]],
                "위험백분위": [
                    selected["주요위험백분위"],
                    selected["보조위험백분위"],
                ],
            }
        )
        st.dataframe(evidence, hide_index=True, use_container_width=True)
        st.markdown(
            f"""
            <div class="dc-policy">
                <strong>권장 관리방향</strong><br>
                {selected["권장관리방향"]}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("#### 행정동 우선순위")
    display_columns = [
        "DLFI_순위",
        "시군구",
        "행정동",
        "DLFI",
        "주위험유형",
        "보조위험유형",
        "분류명확도",
        "권장관리방향",
    ]
    st.dataframe(
        filtered[display_columns],
        hide_index=True,
        use_container_width=True,
        height=310,
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
            "행정동코드 또는 행정동명을 기준으로 위험지도가 자동 연결됩니다."
        )
    else:
        try:
            map_geojson, matched, total = prepare_map_geojson(geojson_data, master)
            render_map(map_geojson)
            st.caption(f"GeoJSON 매칭: {matched}/{total}개 경계")
        except ValueError as error:
            st.error(str(error))

with tab_policy:
    show_policy_package(selected)
    st.markdown("---")
    show_what_if(selected)

with tab_compare:
    st.markdown("#### 두 지역 위험도 비교")
    col_a, col_b = st.columns(2)
    regions = master["지역명"].tolist()
    with col_a:
        region_a = st.selectbox("비교지역 A", regions, index=0, key="region_a")
    with col_b:
        region_b = st.selectbox(
            "비교지역 B",
            regions,
            index=1 if len(regions) > 1 else 0,
            key="region_b",
        )
    row_a = master.loc[master["지역명"] == region_a].iloc[0]
    row_b = master.loc[master["지역명"] == region_b].iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric(region_a, f'DLFI {row_a["DLFI"]:.2f}', row_a["주위험유형"], delta_color="off")
    c2.metric(region_b, f'DLFI {row_b["DLFI"]:.2f}', row_b["주위험유형"], delta_color="off")
    c3.metric("DLFI 차이", f'{abs(float(row_a["DLFI"]) - float(row_b["DLFI"])):.2f}')
    st.altair_chart(comparison_chart(row_a, row_b), use_container_width=True)

    differences = {
        label: float(row_a[column]) - float(row_b[column])
        for label, column in RISK_COLUMNS.items()
    }
    largest = max(differences, key=lambda key: abs(differences[key]))
    higher = region_a if differences[largest] > 0 else region_b
    st.info(
        f"가장 큰 차이는 **{largest} 위험**이며, "
        f"**{higher}**이(가) {abs(differences[largest]):.1f}백분위p 더 높습니다."
    )

with tab_connection:
    st.markdown("#### 다른 팀원 기능과 화면 연결")
    card_1, card_2, card_3 = st.columns(3)
    with card_1:
        st.markdown(
            """
            <div class="dc-link-card">
                <h4>① 하역공간 후보지·운영시간</h4>
                선택 행정동의 하역공간 후보지, 적합도, 권장 운영시간을 연결합니다.
            </div>
            """,
            unsafe_allow_html=True,
        )
    with card_2:
        st.markdown(
            """
            <div class="dc-link-card">
                <h4>③ 정책 What-if</h4>
                하역면 수와 배송 분산율을 조절해 가정 기반 DLFI 변화를 비교합니다.
            </div>
            """,
            unsafe_allow_html=True,
        )
    with card_3:
        st.markdown(
            """
            <div class="dc-link-card">
                <h4>④ 데이터 신뢰도</h4>
                데이터 최신성·직접성·완전성·근거점수와 품질 플래그를 확인합니다.
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("#### ① 하역공간 후보지 연결 결과")
    if loading_candidates is None:
        st.info(
            "`loading_zone_candidates.csv`가 추가되면 선택 행정동을 기준으로 "
            "후보지명·적합도·권장운영시간을 자동 표시합니다."
        )
        st.code(
            "필수 컬럼: 시군구, 행정동, 후보지명, 적합도, 권장운영시간\n"
            "선택 컬럼: 예상수혜세대, 예상수혜상점, 후보지유형",
            language="text",
        )
    else:
        required_loading = ["시군구", "행정동", "후보지명", "적합도", "권장운영시간"]
        missing_loading = [
            column for column in required_loading if column not in loading_candidates.columns
        ]
        if missing_loading:
            st.warning(f"후보지 파일 컬럼 누락: {', '.join(missing_loading)}")
        else:
            selected_candidates = loading_candidates[
                (loading_candidates["시군구"] == selected["시군구"])
                & (loading_candidates["행정동"] == selected["행정동"])
            ].sort_values("적합도", ascending=False)
            if selected_candidates.empty:
                st.warning("선택 행정동의 후보지가 없습니다.")
            else:
                st.dataframe(
                    selected_candidates,
                    hide_index=True,
                    use_container_width=True,
                )

    st.markdown("---")
    show_what_if(selected)

with tab_quality:
    st.markdown("#### 데이터 신뢰도·품질관리 레이어")
    if reliability is None:
        st.info(
            "`reliability_master.csv`를 앱 폴더에 추가하면 "
            "선택 행정동의 데이터 신뢰도를 자동 표시합니다."
        )
    else:
        reliability["행정동코드"] = (
            reliability["행정동코드"]
            .astype("string")
            .str.replace(r"\.0$", "", regex=True)
        )
        quality_row = reliability[
            reliability["행정동코드"] == str(selected["행정동코드"])
        ]
        if quality_row.empty:
            st.warning("선택 행정동의 신뢰도 데이터가 없습니다.")
        else:
            quality = quality_row.iloc[0]
            q1, q2, q3, q4 = st.columns(4)
            q1.metric("종합 신뢰도", f'{float(quality["데이터신뢰도"]):.2f}')
            q2.metric("신뢰도 등급", quality["신뢰도등급"])
            q3.metric("데이터 수단 수", int(quality["데이터수단수"]))
            q4.metric("정책판단", quality["정책판단구분"])

            quality_chart_data = pd.DataFrame(
                {
                    "품질요인": ["최신성", "직접성", "완전성", "근거"],
                    "점수": [
                        quality["s_최신성"],
                        quality["s_직접성"],
                        quality["s_완전성"],
                        quality["s_근거"],
                    ],
                }
            )
            st.altair_chart(
                gray_bar_chart(quality_chart_data, "점수", "품질요인"),
                use_container_width=True,
            )
            st.caption(f'품질 플래그: {quality["품질플래그"]}')

    if registry is not None:
        with st.expander("활용 데이터 출처 보기"):
            st.dataframe(registry, hide_index=True, use_container_width=True, height=300)

    with st.expander("위험유형 분류 기준 보기"):
        st.dataframe(rules, hide_index=True, use_container_width=True, height=300)

