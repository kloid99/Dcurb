from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.feedback import save_feedback
from modules.map_data import build_location_marker, marker_deck
from modules.tram_events import has_tram_control
from modules.weather_api import load_weather_snapshot


def render_driver_view(master: pd.DataFrame, data: dict[str, pd.DataFrame]) -> None:
    st.subheader("4. 배송기사 현장지원")
    st.caption("현장에서 바로 확인할 수 있도록 추천 하역시간, 주의사항, 위치, 피드백 입력을 간단하게 제공합니다.")

    driver = data["driver_time"]
    left, right = st.columns([0.35, 0.65], gap="large")

    with left:
        st.markdown("#### 현장 선택")
        dong = st.selectbox("행정동 선택", master.sort_values("순위")["행정동"], key="driver_dong")
        risk = master[master["행정동"] == dong].iloc[0]
        weather = load_weather_snapshot()
        tram_alert = has_tram_control(data["tram"], dong)

        st.metric("현재 DLFI", f"{pd.to_numeric(risk.get('DLFI_최종점수'), errors='coerce'):.1f}")
        st.metric("우선순위", str(risk.get("우선순위등급", "-")))
        st.warning(f"주의: 날씨 {weather.get('risk', '보통')} / {'트램 통제 영향' if tram_alert else '트램 영향 없음'}")

        st.markdown("#### 현장 피드백")
        feedback_type = st.selectbox("피드백 유형", ["하역공간 부족", "혼잡 심함", "단속 위험", "안전 위험", "기타"])
        memo = st.text_area("메모", placeholder="예: 14~17시 하역공간 부족, 진입로 혼잡")
        if st.button("피드백 저장", width="stretch"):
            save_feedback(dong, feedback_type, memo)
            st.success("피드백이 저장되었습니다.")

    with right:
        top_col, map_col = st.columns([0.48, 0.52], gap="large")
        with top_col:
            render_recommendation_card(driver, dong, risk)
        with map_col:
            render_field_map(master, data, dong)

        st.markdown("#### 시간대별 현장 판단")
        render_timeband_table(driver, dong)


def render_recommendation_card(driver: pd.DataFrame, dong: str, risk: pd.Series) -> None:
    if driver.empty:
        st.info("기사 시간대 데이터가 없습니다.")
        return

    view = driver[driver["행정동"] == dong].copy()
    if view.empty:
        st.info("선택 행정동의 시간대 데이터가 없습니다.")
        return

    view["하역추천점수_시간대"] = pd.to_numeric(view["하역추천점수_시간대"], errors="coerce").fillna(0)
    best = view.sort_values("하역추천점수_시간대", ascending=False).iloc[0]
    score = best["하역추천점수_시간대"]
    grade = best.get("탄력하역권_등급_표시", best.get("탄력하역권_등급", "-"))
    policy = risk.get("추천정책_텍스트", "안전 운행 바랍니다.")

    st.markdown("#### 오늘의 추천")
    c1, c2 = st.columns(2)
    c1.metric("추천 하역시간", f"{best.get('시간대', '-')}시")
    c2.metric("추천점수", f"{score:.1f}")
    st.success(f"운영 판단: {grade}")
    st.info(f"기사 안내문구: {policy}")

    if "모델실측_검증플래그" in best.index and pd.notna(best["모델실측_검증플래그"]):
        st.caption(f"검증 플래그: {best['모델실측_검증플래그']}")


def render_field_map(master: pd.DataFrame, data: dict[str, pd.DataFrame], dong: str) -> None:
    st.markdown("#### 현장 위치")
    marker = build_location_marker(dong, data["weather_location"])
    if marker.empty:
        st.info("현장 위치 좌표가 없습니다.")
        return
    deck = marker_deck(marker)
    if deck is None:
        st.map(
            marker,
            latitude="latitude",
            longitude="longitude",
            size="map_size",
            color="map_color",
            zoom=13,
            height=330,
            width="stretch",
        )
    else:
        st.pydeck_chart(deck, height=330, width="stretch")
    st.caption("행정동 중심 좌표 기준 위치입니다. 실제 하역 지점은 현장 안내와 도로 여건을 우선 확인하세요.")


def render_timeband_table(driver: pd.DataFrame, dong: str) -> None:
    if driver.empty:
        return
    view = driver[driver["행정동"] == dong].copy()
    if view.empty:
        return
    show_cols = [
        "시간대",
        "하역추천점수_시간대",
        "탄력하역권_등급",
        "혼잡도_시간대",
        "배송집중도_시간대",
        "안전취약점수",
        "모델실측_검증플래그",
    ]
    show_cols = [column for column in show_cols if column in view.columns]
    view["하역추천점수_시간대"] = pd.to_numeric(view["하역추천점수_시간대"], errors="coerce").fillna(0)
    st.dataframe(
        view[show_cols].sort_values("하역추천점수_시간대", ascending=False),
        width="stretch",
        hide_index=True,
    )
