from __future__ import annotations

import pandas as pd
import streamlit as st


def render_weather_view(master: pd.DataFrame, data: dict[str, pd.DataFrame]) -> None:
    st.subheader("6. 날씨 리스크")
    st.caption("Open-Meteo 7일 예보 원본과 시간대·구·행정동 가공 결과를 분리해서 확인합니다.")

    hourly = data.get("openmeteo_hourly", pd.DataFrame())
    timeblock = data.get("openmeteo_timeblock", pd.DataFrame())
    gu_summary = data.get("openmeteo_gu_summary", pd.DataFrame())
    dong_daily = data.get("openmeteo_dong_daily", pd.DataFrame())
    top10 = data.get("openmeteo_top10", pd.DataFrame())
    quality = data.get("openmeteo_quality", pd.DataFrame())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("API 원본 결합", f"{len(hourly):,}행")
    c2.metric("시간대 가공", f"{len(timeblock):,}행")
    c3.metric("행정동·일 요약", f"{len(dong_daily):,}행")
    c4.metric("품질보고서", f"{len(quality):,}행")

    st.markdown("#### 날씨 데이터 계보")
    lineage = pd.DataFrame(
        [
            ["daejeon_openmeteo_hourly_7days.csv", "API 원본 응답 + 행정동 결합", len(hourly)],
            ["daejeon_openmeteo_timeblock_7days.csv", "6개 시간대 집계", len(timeblock)],
            ["daejeon_openmeteo_gu_summary_7days.csv", "구 단위 요약", len(gu_summary)],
            ["daejeon_openmeteo_dong_daily_7days.csv", "행정동·일 단위 요약", len(dong_daily)],
            ["daejeon_openmeteo_weather_top10_7days.csv", "날씨 위험점수 TOP10", len(top10)],
            ["daejeon_openmeteo_7days_quality_report.csv", "행 수·중복·결측 품질검증", len(quality)],
        ],
        columns=["파일", "역할", "행수"],
    )
    st.dataframe(lineage, width="stretch", hide_index=True)

    filters, contents = st.columns([0.25, 0.75], gap="large")
    with filters:
        st.markdown("#### 필터")
        source = st.radio("데이터 보기", ["위험 TOP10", "시간대", "구 요약", "행정동·일", "품질보고서", "API 원본"], index=0)
        gu = "전체"
        dong = "전체"
        if not timeblock.empty:
            gu_col = first_existing(timeblock, ["gu_name", "시군구"])
            dong_col = first_existing(timeblock, ["location_name", "행정동"])
            if gu_col:
                gu = st.selectbox("구", ["전체"] + sorted(timeblock[gu_col].dropna().astype(str).unique().tolist()))
            if dong_col:
                dong = st.selectbox("행정동", ["전체"] + sorted(timeblock[dong_col].dropna().astype(str).unique().tolist()))

    with contents:
        if source == "위험 TOP10":
            render_table(top10, gu, dong)
        elif source == "시간대":
            render_table(timeblock, gu, dong)
            render_weather_chart(timeblock, gu, dong)
        elif source == "구 요약":
            render_table(gu_summary, gu, "전체")
        elif source == "행정동·일":
            render_table(dong_daily, gu, dong)
        elif source == "품질보고서":
            render_table(quality, "전체", "전체")
        else:
            render_table(hourly.head(1000), gu, dong)


def first_existing(df: pd.DataFrame, columns: list[str]) -> str | None:
    return next((column for column in columns if column in df.columns), None)


def render_table(df: pd.DataFrame, gu: str, dong: str) -> None:
    if df.empty:
        st.info("표시할 데이터가 없습니다.")
        return
    view = df.copy()
    gu_col = first_existing(view, ["gu_name", "시군구"])
    dong_col = first_existing(view, ["location_name", "행정동"])
    if gu != "전체" and gu_col:
        view = view[view[gu_col].astype(str) == gu]
    if dong != "전체" and dong_col:
        view = view[view[dong_col].astype(str) == dong]
    st.dataframe(view.head(500), width="stretch", hide_index=True)


def render_weather_chart(df: pd.DataFrame, gu: str, dong: str) -> None:
    if df.empty:
        return
    view = df.copy()
    gu_col = first_existing(view, ["gu_name", "시군구"])
    dong_col = first_existing(view, ["location_name", "행정동"])
    if gu != "전체" and gu_col:
        view = view[view[gu_col].astype(str) == gu]
    if dong != "전체" and dong_col:
        view = view[view[dong_col].astype(str) == dong]

    time_col = first_existing(view, ["time_block", "시간대"])
    chart_cols = [
        column
        for column in ["weather_risk_score", "max_rain_probability", "total_precipitation_mm", "max_wind_speed"]
        if column in view.columns
    ]
    if time_col and chart_cols:
        chart = view.groupby(time_col)[chart_cols].mean(numeric_only=True)
        st.markdown("#### 시간대 평균 날씨 리스크")
        st.line_chart(chart)
