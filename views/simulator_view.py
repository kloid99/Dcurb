from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.load_data import safe_float
from modules.policy_simulator import simulate_policy
from modules.tram_events import has_tram_control
from modules.weather_api import WEATHER_SCENARIOS


def render_simulator_view(master: pd.DataFrame, data: dict[str, pd.DataFrame]) -> None:
    st.subheader("2. 정책 시뮬레이터")

    c1, c2 = st.columns([1, 2])
    with c1:
        dong = st.selectbox("행정동 선택", master.sort_values("순위")["행정동"], key="sim_dong")
        loading_bays = st.slider("임시 하역면 수", 0, 20, 4)
        dispersion = st.slider("배송 분산율", 0, 60, 20, step=5)
        weather_name = st.selectbox("날씨 시나리오", list(WEATHER_SCENARIOS.keys()))
        tram_default = has_tram_control(data["tram"], dong)
        tram_control = st.toggle("트램 통제 반영", value=tram_default)

    risk = master[master["행정동"] == dong].iloc[0]
    result = simulate_policy(
        risk,
        loading_bays=loading_bays,
        delivery_dispersion_rate=dispersion,
        weather_multiplier=WEATHER_SCENARIOS[weather_name],
        tram_control=tram_control,
    )

    with c2:
        m1, m2, m3 = st.columns(3)
        m1.metric("적용 전 DLFI", f"{result['before_score']:.1f}")
        m2.metric("적용 후 DLFI", f"{result['after_score']:.1f}")
        m3.metric("변화", f"{result['delta']:.1f}")
        st.bar_chart(pd.DataFrame({"적용 전": result["before"], "적용 후": result["after"]}))

    st.caption(
        f"현재 선택: {risk['시군구']} {dong} / 기본 DLFI {safe_float(risk.get('DLFI_최종점수')):.1f} / "
        f"날씨 {weather_name} / 트램 {'반영' if tram_control else '미반영'}"
    )
