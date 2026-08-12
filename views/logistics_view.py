from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.map_data import build_location_marker, marker_deck
from modules.tram_events import tram_for_dong


def render_logistics_view(master: pd.DataFrame, data: dict[str, pd.DataFrame]) -> None:
    st.subheader("3. 물류기업 운영지원")
    st.caption("시간대별 배송집중도와 혼잡도를 비교해 배송 분산 권장 시간대를 찾습니다.")

    logistics = data["logistics_time"]
    if logistics.empty:
        st.info("물류기업 시간대 데이터가 없습니다.")
        return

    c1, c2 = st.columns([1, 2])
    with c1:
        district_options = ["전체"] + sorted(logistics["시군구"].dropna().unique().tolist())
        district = st.selectbox("시군구", district_options, key="logi_gu")
        filtered = logistics if district == "전체" else logistics[logistics["시군구"] == district]
        dong = st.selectbox("행정동", sorted(filtered["행정동"].dropna().unique()), key="logi_dong")

    view = logistics[logistics["행정동"] == dong].copy()
    with c2:
        st.markdown("#### 시간대별 배송집중도·혼잡도")
        chart_cols = [column for column in ["배송집중도_시간대", "혼잡도_시간대"] if column in view.columns]
        if chart_cols:
            st.line_chart(view.set_index("시간대")[chart_cols])
        else:
            st.info("차트 표시용 시간대 컬럼이 없습니다.")

    map_df = build_location_marker(dong, data["weather_location"])
    if not map_df.empty:
        st.markdown("#### 운영 대상 위치")
        deck = marker_deck(map_df)
        if deck is None:
            st.map(
                map_df,
                latitude="latitude",
                longitude="longitude",
                size="map_size",
                color="map_color",
                zoom=12,
                height=300,
                width="stretch",
            )
        else:
            st.pydeck_chart(deck, height=300, width="stretch")

    tram = tram_for_dong(data["tram"], dong)
    if tram.empty:
        st.success("트램 영향 지역 알림: 현재 등록된 통제 영향 없음")
    else:
        st.warning("트램 영향 지역 알림: 통제 영향 후보 지역입니다.")
        st.dataframe(tram, width="stretch", hide_index=True)

    if "배송집중도_시간대" in view.columns and "혼잡도_시간대" in view.columns:
        rec = view.assign(
            분산추천점수=pd.to_numeric(view["배송집중도_시간대"], errors="coerce").fillna(0)
            - pd.to_numeric(view["혼잡도_시간대"], errors="coerce").fillna(0) * 0.35
        ).sort_values("분산추천점수")
        st.markdown("#### 배송 분산 권장 시간대")
        st.dataframe(
            rec[["시간대", "배송집중도_시간대", "혼잡도_시간대", "분산추천점수"]],
            width="stretch",
            hide_index=True,
        )
