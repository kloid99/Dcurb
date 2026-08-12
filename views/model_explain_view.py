from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.reliability import reliability_summary


def render_model_explain_view(master: pd.DataFrame, data: dict[str, pd.DataFrame]) -> None:
    st.subheader("5. 데이터·모델 설명")

    st.markdown("#### 공식 모델 채택 이유")
    st.write(
        "DLFI 기반 고위험 여부를 행정동 단위로 설명하기 위해 예측 성능, 해석 가능성, 정책 연결성을 함께 고려했습니다. "
        "현재 데이터에는 RandomForest 예측 결과와 K-Means 위험유형, RuleBased 정책추천 결과가 통합되어 있습니다."
    )

    cols = st.columns(3)
    if "공식모델_Accuracy" in master.columns:
        cols[0].metric("Accuracy", f"{pd.to_numeric(master['공식모델_Accuracy'], errors='coerce').mean():.3f}")
    if "공식모델_F1" in master.columns:
        cols[1].metric("F1", f"{pd.to_numeric(master['공식모델_F1'], errors='coerce').mean():.3f}")
    if "공식모델_AUC" in master.columns:
        cols[2].metric("AUC", f"{pd.to_numeric(master['공식모델_AUC'], errors='coerce').mean():.3f}")

    st.markdown("#### 변수 중요도")
    shap_cols = [c for c in ["SHAP_TOP1_변수", "SHAP_TOP2_변수", "SHAP_TOP3_변수", "기여변수_표시"] if c in master.columns]
    if shap_cols:
        counts = pd.concat([master[c] for c in shap_cols], ignore_index=True).dropna().value_counts().head(10)
        st.bar_chart(counts)

    st.markdown("#### 군집 유형 설명")
    risk_col = "위험유형" if "위험유형" in master.columns else "주위험유형"
    if risk_col in master.columns:
        st.dataframe(master[risk_col].value_counts().reset_index(), width="stretch", hide_index=True)

    st.markdown("#### 신뢰도 산정 방식")
    summary = reliability_summary(master)
    if summary["avg"] is not None:
        st.metric("평균 데이터 신뢰도", f"{summary['avg']:.1f}")
        st.metric("신뢰도 70 미만 행정동", f"{summary['low_count']}개")
    st.write("최신성, 직접성, 완전성, 근거 점수를 종합해 행정동별 데이터 신뢰도를 산정했습니다.")

    st.markdown("#### 한계 및 향후 보강 데이터")
    st.write(
        "- 실제 배송지연·민원·운영 문제 이력은 아직 제한적입니다.\n"
        "- 시간대별 단속, 도로폭·차로수, 실시간 트램 통제, 현장 피드백 누적 데이터가 추가되면 일반화 검증력이 높아집니다.\n"
        "- 현재 결과는 현장검토 후보지를 좁히는 정책지원용 지표로 해석해야 합니다."
    )

    st.markdown("#### Open-Meteo 7일 날씨 데이터 계보")
    lineage = pd.DataFrame(
        [
            {
                "파일": "daejeon_openmeteo_hourly_7days.csv",
                "구분": "API 원본 결합",
                "설명": "Open-Meteo API 원본 응답을 행정동 정보와 결합",
                "행수": len(data.get("openmeteo_hourly", pd.DataFrame())),
            },
            {
                "파일": "daejeon_openmeteo_timeblock_7days.csv",
                "구분": "가공",
                "설명": "API 원본을 6개 시간대로 집계",
                "행수": len(data.get("openmeteo_timeblock", pd.DataFrame())),
            },
            {
                "파일": "daejeon_openmeteo_gu_summary_7days.csv",
                "구분": "가공",
                "설명": "시간대 파일을 구 단위로 요약",
                "행수": len(data.get("openmeteo_gu_summary", pd.DataFrame())),
            },
            {
                "파일": "daejeon_openmeteo_dong_daily_7days.csv",
                "구분": "가공",
                "설명": "시간대 파일을 행정동·일 단위로 요약",
                "행수": len(data.get("openmeteo_dong_daily", pd.DataFrame())),
            },
            {
                "파일": "daejeon_openmeteo_weather_top10_7days.csv",
                "구분": "가공",
                "설명": "계산된 위험점수 기준 TOP10",
                "행수": len(data.get("openmeteo_top10", pd.DataFrame())),
            },
            {
                "파일": "daejeon_openmeteo_7days_quality_report.csv",
                "구분": "품질보고서",
                "설명": "행 수·중복·결측 검증",
                "행수": len(data.get("openmeteo_quality", pd.DataFrame())),
            },
        ]
    )
    st.dataframe(lineage, width="stretch", hide_index=True)

    top10 = data.get("openmeteo_top10", pd.DataFrame())
    if not top10.empty:
        with st.expander("Open-Meteo 위험 TOP10 확인"):
            st.dataframe(top10.head(50), width="stretch", hide_index=True)
