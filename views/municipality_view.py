from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.candidate_sites import recommend_candidates
from modules.event_risk import event_adjusted_top
from modules.load_data import safe_float, to_num
from modules.map_data import build_dong_map, build_service_radius, risk_map_deck, service_radius_deck
from modules.policy_simulator import simulate_loading_zone
from modules.tram_events import has_tram_control
from modules.weather_api import weather_for_dong


TIME_SLOTS = ["07~10", "10~12", "12~14", "14~17", "17~20", "20~23"]


def render_municipality_view(master: pd.DataFrame, data: dict[str, pd.DataFrame]) -> None:
    st.subheader("1. 지자체 정책지원")
    st.caption("지자체 담당자가 오늘 어디를 먼저 보고, 어떤 정책 패키지를 검토해야 하는지 한 화면에서 판단합니다.")

    selected_risk, inputs = render_today_summary_and_filters(master, data)
    render_risk_map(master, data, selected_risk)
    render_differentiated_features(master, data, selected_risk, inputs)


def render_today_summary_and_filters(master: pd.DataFrame, data: dict[str, pd.DataFrame]) -> tuple[pd.Series, dict]:
    high_risk = int(to_num(master.get("고위험여부", pd.Series(dtype=float))).sum())
    event_top = event_adjusted_top(master).iloc[0]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("오늘의 고위험 행정동", f"{high_risk}개")
    k2.metric("DLFI 최고점", f"{master['DLFI_최종점수'].max():.1f}")
    k3.metric("상황반영 최고위험", event_top["행정동"])
    k4.metric("평균 분석 신뢰도", f"{safe_float(master.get('데이터신뢰도', pd.Series(dtype=float)).mean(), 0):.1f}")

    st.markdown("#### 오늘의 상황위험 요약")
    left, right = st.columns([0.34, 0.66], gap="large")

    with left:
        district_options = ["전체"] + sorted(master["시군구"].dropna().unique().tolist())
        district = st.selectbox("시군구", district_options, key="muni_gu")
        filtered = master if district == "전체" else master[master["시군구"] == district]
        filtered = filtered.sort_values("순위")
        dong = st.selectbox("행정동", filtered["행정동"], key="muni_dong")
        slot = st.selectbox("운영시간", TIME_SLOTS, index=3, key="muni_slot")
        bays = st.slider("임시 하역면 수", 1, 10, 3, key="muni_bays")
        policy_mode = st.radio("정책 우선기준", ["효과 우선", "실행 가능성 우선"], horizontal=True)

    with right:
        top_a, top_b = st.columns(2)
        with top_a:
            st.markdown("##### DLFI TOP10")
            top10 = master.sort_values("DLFI_최종점수", ascending=False).head(10)
            st.dataframe(
                top10[["순위", "시군구", "행정동", "DLFI_최종점수", "우선순위등급", "위험유형"]],
                width="stretch",
                hide_index=True,
            )
        with top_b:
            st.markdown("##### 상황반영 TOP10")
            adjusted = event_adjusted_top(master).head(10)
            score_col = "상황반영_DLFI" if "상황반영_DLFI" in adjusted.columns else "DLFI_최종점수"
            st.dataframe(
                adjusted[["순위", "시군구", "행정동", score_col, "추천정책_텍스트"]],
                width="stretch",
                hide_index=True,
            )

    start_hour, end_hour = [int(value) for value in slot.split("~")]
    inputs = {
        "bays": bays,
        "start_hour": start_hour,
        "end_hour": end_hour,
        "service_minutes": 20,
        "utilization": 0.6,
        "policy_mode": policy_mode,
        "slot": slot,
    }
    selected = master[master["행정동"] == dong].iloc[0]
    return selected, inputs


def render_risk_map(master: pd.DataFrame, data: dict[str, pd.DataFrame], selected: pd.Series) -> None:
    st.markdown("#### 행정동 DLFI 위험지도")
    st.caption("지도는 행정동 중심 좌표 기준입니다. 후보지의 정확한 설치 지점은 현장조사 후 확정해야 하므로, 지도에는 가짜 후보 점을 찍지 않습니다.")
    map_df = build_dong_map(master, data["weather_location"], selected_dong=selected["행정동"])
    if map_df.empty:
        st.info("지도 표시용 행정동 좌표 데이터가 없습니다.")
        return
    deck = risk_map_deck(map_df, selected["행정동"])
    if deck is None:
        st.map(
            map_df,
            latitude="latitude",
            longitude="longitude",
            size="map_size",
            color="map_color",
            zoom=10,
            height=470,
            width="stretch",
        )
    else:
        st.pydeck_chart(deck, height=470, width="stretch")


def render_differentiated_features(
    master: pd.DataFrame,
    data: dict[str, pd.DataFrame],
    selected: pd.Series,
    inputs: dict,
) -> None:
    st.markdown("#### 행정동 상세 및 차별화 기능")
    render_feature_flow()

    candidates = recommend_candidates(selected, data["elastic_segments"], inputs)
    best = candidates.iloc[0]
    impact = simulate_loading_zone(selected, best["적합도"], inputs)
    service_map = build_service_radius(selected, data["weather_location"], int(best.get("서비스반경_m", 420)))
    time_data = data["driver_time"]
    selected_time = pd.DataFrame()
    if not time_data.empty and "행정동" in time_data.columns:
        selected_time = time_data[time_data["행정동"] == selected["행정동"]].copy()

    detail_left, detail_right = st.columns([0.54, 0.46], gap="large")
    with detail_left:
        st.markdown("##### 위험 행정동 카드")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("기본 DLFI", f"{safe_float(selected.get('DLFI_최종점수')):.1f}")
        m2.metric("고위험 예측확률", f"{safe_float(selected.get('고위험예측확률')):.2f}")
        m3.metric("위험유형", str(selected.get("위험유형", "-")))
        m4.metric("분석 신뢰도", str(selected.get("신뢰도등급", "확인 필요")))
        st.info(
            f"주요 기여변수: {selected.get('기여변수_표시', '-')} / "
            f"날씨·트램 보정: {'트램 영향' if has_tram_control(data['tram'], selected['행정동']) else '일반'}"
        )
        st.success(f"정책추천 카드: {selected.get('추천정책_텍스트', '정책추천 정보 없음')}")

        st.markdown("##### 주요 위험요인 TOP3")
        st.dataframe(build_risk_factor_table(selected), width="stretch", hide_index=True)

        st.markdown("##### 1) 하역공간 우선 설치 시뮬레이터")
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("설치 전", f"{impact['before_dlfi']:.1f}")
        s2.metric("설치 후", f"{impact['after_dlfi']:.1f}")
        s3.metric("예상 변화", f"{impact['delta']:.1f}")
        s4.metric("유효 처리량", f"{impact['effective_capacity']:.0f}대")
        st.bar_chart(pd.DataFrame({"설치 전": impact["before"], "설치 후": impact["after"]}))

    with detail_right:
        st.markdown("##### 서비스 반경 지도")
        if service_map.empty:
            st.info("서비스 반경 지도 데이터가 없습니다.")
        else:
            deck = service_radius_deck(service_map)
            if deck is None:
                st.map(
                    service_map,
                    latitude="latitude",
                    longitude="longitude",
                    size="map_size",
                    color="map_color",
                    zoom=12,
                    height=360,
                    width="stretch",
                )
            else:
                st.pydeck_chart(deck, height=360, width="stretch")
        st.caption("후보지 좌표가 없는 경우 행정동 중심 기준 서비스 반경으로만 표시합니다.")

        st.markdown("##### 2) 정책 패키지 추천")
        policy_package = classify_policy_package(selected)
        st.write(policy_package)

    lower1, lower2 = st.columns(2, gap="large")
    with lower1:
        st.markdown("##### 3) 하역권·마이크로 거점 후보지 추천")
        st.dataframe(
            candidates[
                [
                    "후보지명",
                    "후보지유형",
                    "도로명",
                    "구간",
                    "기존허용시간",
                    "주차면수",
                    "서비스반경_m",
                    "적합도",
                    "source",
                ]
            ],
            width="stretch",
            hide_index=True,
        )

    with lower2:
        st.markdown("##### 4) 위험유형 자동 분류 + 시간대 추천")
        st.write(
            {
                "위험유형": selected.get("위험유형", "-"),
                "주요 기여변수": selected.get("기여변수_표시", "-"),
                "우선순위등급": selected.get("우선순위등급", "-"),
            }
        )
        if selected_time.empty:
            st.info("선택 행정동의 시간대 추천 데이터가 없습니다.")
        else:
            show_cols = [
                "시간대",
                "하역추천점수_시간대",
                "탄력하역권_등급",
                "혼잡도_시간대",
                "배송집중도_시간대",
                "모델실측_검증플래그",
            ]
            st.dataframe(
                selected_time[[c for c in show_cols if c in selected_time.columns]].sort_values(
                    "하역추천점수_시간대", ascending=False
                ),
                width="stretch",
                hide_index=True,
            )

    st.markdown("##### 5) 경쟁지표 비교 카드: 단속 중심 vs DLFI 복합지수")
    comparison = build_competitor_comparison(master)
    st.dataframe(comparison, width="stretch", hide_index=True)

    st.markdown("##### 데이터 신뢰도 판단")
    st.dataframe(build_reliability_decision(selected), width="stretch", hide_index=True)

    weather = weather_for_dong(data["weather_time"], selected["행정동"])
    if not weather.empty:
        with st.expander("날씨 보정 데이터 확인"):
            st.dataframe(weather.head(100), width="stretch", hide_index=True)


def classify_policy_package(row: pd.Series) -> str:
    factors = str(row.get("기여변수_표시", "")) + "|" + str(row.get("위험유형", ""))
    packages = []
    if "단속" in factors:
        packages.append("단속반복형: 탄력 하역권 지정, 단속구간 안내 강화")
    if "보행" in factors:
        packages.append("보행충돌형: 등하교·퇴근 혼잡 시간대 회피, 안전 완충구간 검토")
    if "배송" in factors or "상권" in factors:
        packages.append("배송수요과밀형: 공동배송 시간 분산, 마이크로 거점 우선 검토")
    if "안전" in factors:
        packages.append("안전취약형: 보호구역 주변 운영시간 제한, 현장 안전표지 보강")
    if not packages:
        packages.append("기본관리형: 모니터링 유지, 민원·피드백 누적 후 재평가")
    return "\n\n".join(packages)


def render_feature_flow() -> None:
    flow = pd.DataFrame(
        [
            ["1", "위험지역 탐지", "DLFI·상황반영 TOP10으로 우선 검토 행정동 식별"],
            ["2", "원인 설명", "위험유형, 주요 기여변수 TOP3, 시간대 위험 확인"],
            ["3", "공간 대안 제시", "하역권·마이크로 거점 후보지와 서비스 반경 제시"],
            ["4", "정책효과 시뮬레이션", "하역면·운영시간 조건에 따른 적용 전후 DLFI 비교"],
            ["5", "신뢰도·비교 검증", "데이터 신뢰도와 단속 중심 방식 대비 차별성 확인"],
        ],
        columns=["단계", "차별화 기능", "구현 내용"],
    )
    st.dataframe(flow, width="stretch", hide_index=True)


def build_risk_factor_table(row: pd.Series) -> pd.DataFrame:
    factors = [
        ("배송수요", safe_float(row.get("배송수요점수_최종", 0))),
        ("교통방해", safe_float(row.get("교통방해점수", 0))),
        ("보행충돌", safe_float(row.get("보행충돌점수_최종", 0))),
        ("단속반복", safe_float(row.get("단속반복점수", 0))),
        ("안전취약", safe_float(row.get("안전취약점수", 0))),
        ("하역부족", safe_float(row.get("하역부족위험", 100 - safe_float(row.get("하역여유점수", 0))))),
    ]
    top = sorted(factors, key=lambda item: item[1], reverse=True)[:3]
    return pd.DataFrame(
        [{"순위": index + 1, "위험요인": name, "점수": round(value, 1), "해석": explain_factor(name)} for index, (name, value) in enumerate(top)]
    )


def explain_factor(name: str) -> str:
    mapping = {
        "배송수요": "배송 수요가 집중되어 하역 수요가 커질 가능성",
        "교통방해": "차로 점유와 혼잡으로 물류 마찰 증가 가능성",
        "보행충돌": "보행자와 배송차량 동선 충돌 가능성",
        "단속반복": "상습 불법정차·단속 발생 가능성",
        "안전취약": "보호구역·취약시설 등 안전 리스크",
        "하역부족": "수요 대비 하역 여유 공간 부족",
    }
    return mapping.get(name, "추가 확인 필요")


def build_reliability_decision(row: pd.Series) -> pd.DataFrame:
    score = safe_float(row.get("데이터신뢰도", 0))
    grade = row.get("신뢰도등급", "확인 필요")
    if score >= 85:
        decision = "시범사업 후보지 검토 가능"
    elif score >= 70:
        decision = "현장 확인 후 정책 판단"
    elif score >= 50:
        decision = "추가 데이터 보강 우선"
    else:
        decision = "정책 판단 근거로 제한적 활용"
    return pd.DataFrame(
        [
            {"항목": "데이터 신뢰도", "값": f"{score:.1f}", "판단": grade},
            {"항목": "정책 활용 기준", "값": decision, "판단": "분석 과정 보고서에 명시"},
            {"항목": "SHAP 제공 여부", "값": row.get("SHAP제공여부", "-"), "판단": "설명가능성 보조"},
        ]
    )


def build_competitor_comparison(master: pd.DataFrame) -> pd.DataFrame:
    enforcement_col = "단속반복점수"
    if enforcement_col not in master.columns:
        return pd.DataFrame(
            [
                {
                    "비교항목": "단속 중심 랭킹",
                    "일반 접근": "단속 데이터 없음",
                    "D-Curb 접근": "DLFI 복합지표로 보완",
                }
            ]
        )

    dlfi_top = set(master.sort_values("DLFI_최종점수", ascending=False).head(10)["행정동"])
    enforcement_top = set(master.sort_values(enforcement_col, ascending=False).head(10)["행정동"])
    overlap = len(dlfi_top & enforcement_top)
    return pd.DataFrame(
        [
            {
                "비교항목": "분석 단위",
                "일반 접근": "구 단위 또는 단속 위치 중심",
                "D-Curb 접근": "82개 행정동 단위 정책지원",
            },
            {
                "비교항목": "위험 산정",
                "일반 접근": "단속건수·민원 중심",
                "D-Curb 접근": "배송·교통·보행·단속·안전·하역여유 복합",
            },
            {
                "비교항목": "TOP10 차이",
                "일반 접근": f"단속반복 TOP10과 DLFI TOP10 겹침 {overlap}개",
                "D-Curb 접근": "단속만으로 놓치는 배송·보행·안전 위험 보완",
            },
            {
                "비교항목": "데이터 한계 관리",
                "일반 접근": "미매칭 데이터 제외 또는 숨김",
                "D-Curb 접근": "신뢰도·배분·검증 플래그로 투명하게 표시",
            },
            {
                "비교항목": "정책 연결",
                "일반 접근": "순위 제시",
                "D-Curb 접근": "후보지·운영시간·정책 패키지까지 연결",
            },
        ]
    )
