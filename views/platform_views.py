from __future__ import annotations

import math
from datetime import datetime

import pandas as pd
import streamlit as st

from modules.load_data import first_existing, safe_float


SCORE_COLS = [
    "배송수요점수_최종",
    "교통방해점수",
    "보행충돌점수_최종",
    "단속반복점수",
    "안전취약점수",
    "하역부족위험",
    "weather_risk_score_시나리오",
    "tram_event_risk_score",
]


def _score(row: pd.Series, column: str, default: float = 0) -> float:
    return safe_float(row.get(column, default), default)


def _risk_level(score: float) -> tuple[str, str]:
    if score >= 80:
        return "긴급", "danger"
    if score >= 65:
        return "높음", "warn"
    if score >= 45:
        return "중간", "mid"
    return "양호", "safe"


def _top_rows(master: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    if master.empty:
        return master
    score_col = "DLFI_시나리오점수" if "DLFI_시나리오점수" in master.columns else "DLFI_최종점수"
    return master.sort_values(score_col, ascending=False).head(n).copy()


def _top_factors(row: pd.Series, n: int = 3) -> list[tuple[str, float]]:
    labels = {
        "배송수요점수_최종": "택배 물동량",
        "교통방해점수": "이면도로 폭",
        "보행충돌점수_최종": "보행 혼잡",
        "단속반복점수": "정차 신고",
        "안전취약점수": "안전 취약",
        "하역부족위험": "하역공간 부족",
        "weather_risk_score_시나리오": "악천후 위험",
        "tram_event_risk_score": "트램 공사",
    }
    values = [(labels[col], _score(row, col)) for col in SCORE_COLS if col in row.index]
    return sorted(values, key=lambda item: item[1], reverse=True)[:n]


def _bar(label: str, value: float, color: str = "#0f9f8f") -> str:
    width = max(2, min(100, value))
    return (
        "<div class='dc-bar-row'>"
        f"<span>{label}</span>"
        f"<div class='dc-bar-track'><i style='width:{width:.0f}%; background:{color};'></i></div>"
        f"<b>{value:.0f}</b>"
        "</div>"
    )


def render_topbar(title: str, subtitle: str, role_label: str) -> None:
    st.markdown(
        f"""
        <div class="dc-topbar">
          <div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>
          <div class="dc-top-actions">
            <span class="dc-chip-muted">2026.07.25 {datetime.now().strftime('%H:%M')}</span>
            <span class="dc-role-chip">{role_label}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_dcurb_sidebar(menu_options: list[str], role_label: str) -> tuple[str, str]:
    with st.sidebar:
        st.markdown(
            "<div class='dc-brand'><div class='dc-logo'>D</div><div><b>D-Curb</b><span>Guardian</span></div></div>",
            unsafe_allow_html=True,
        )
        st.markdown('<div class="dc-menu-label">메인 메뉴</div>', unsafe_allow_html=True)
        selected = st.radio("메인 메뉴", menu_options, label_visibility="collapsed")

        st.markdown('<div class="dc-menu-label dc-spacer">시나리오</div>', unsafe_allow_html=True)
        scenario = st.radio(
            "시나리오",
            ["통합 데이터 기준", "악천후 보정", "트램 공사 보정"],
            label_visibility="collapsed",
        )

        st.markdown("<div class='dc-sidebar-fill'></div>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='dc-user-card'><div class='dc-avatar'>이</div><div><b>이관리 주무관</b><span>{role_label}</span></div></div>",
            unsafe_allow_html=True,
        )
        if st.button("로그아웃", width="stretch"):
            st.session_state.clear()
            st.rerun()
    return selected, scenario


def render_overview_map(master: pd.DataFrame, data: dict[str, pd.DataFrame], scenario: str) -> None:
    scenario_master = apply_scenario_adjustment(master, data, scenario)
    top = _top_rows(scenario_master, 12)
    dong_names = top["행정동"].tolist()
    default_idx = 0 if dong_names else None
    selected_dong = st.session_state.get("selected_dong", dong_names[0] if dong_names else "")

    chip = st.radio(
        "지도 필터",
        ["전체", "위험만", "주의만", "양호만", "물류 혼잡", "공사 영향", "기상 영향"],
        horizontal=True,
        label_visibility="collapsed",
    )
    left, right = st.columns([0.72, 0.28], gap="large")

    filtered = _filter_master(scenario_master, chip)
    map_rows = _top_rows(filtered, 18)
    with left:
        render_daejeon_board_map(map_rows, selected_dong, scenario)
        st.markdown("<div class='dc-mini-title'>DLFI TOP 위험 행정동</div>", unsafe_allow_html=True)
        cols = st.columns(3)
        for idx, (_, row) in enumerate(top.head(6).iterrows()):
            level, tone = _risk_level(_score(row, "DLFI_시나리오점수", _score(row, "DLFI_최종점수")))
            with cols[idx % 3]:
                if st.button(
                    f"{row['행정동']} · {row['시군구']} · {level}",
                    key=f"pick_{idx}_{row['행정동']}",
                    width="stretch",
                ):
                    st.session_state["selected_dong"] = row["행정동"]
                    selected_dong = row["행정동"]
                    st.rerun()

    with right:
        selected = scenario_master[scenario_master["행정동"] == selected_dong]
        row = selected.iloc[0] if not selected.empty else top.iloc[0]
        render_dong_detail_panel(row, scenario)


def apply_scenario_adjustment(master: pd.DataFrame, data: dict[str, pd.DataFrame], scenario: str) -> pd.DataFrame:
    adjusted = master.copy()
    adjusted["DLFI_기준점수"] = pd.to_numeric(adjusted["DLFI_최종점수"], errors="coerce").fillna(0)
    adjusted["DLFI_시나리오점수"] = adjusted["DLFI_기준점수"]
    adjusted["시나리오_보정점수"] = 0.0
    adjusted["시나리오_근거"] = "통합 데이터 기준 DLFI"

    if scenario == "악천후 보정":
        weather = data.get("openmeteo_timeblock", pd.DataFrame()).copy()
        if not weather.empty and {"행정동", "weather_risk_score"}.issubset(weather.columns):
            weather["weather_risk_score"] = pd.to_numeric(weather["weather_risk_score"], errors="coerce").fillna(0)
            weather_summary = (
                weather.groupby("행정동", as_index=False)
                .agg(
                    weather_risk_score_시나리오=("weather_risk_score", "max"),
                    max_rain_probability_시나리오=("max_rain_probability", "max"),
                    max_wind_gust_시나리오=("max_wind_gust", "max"),
                    weather_risk_reason_시나리오=("weather_risk_reason", lambda x: next((v for v in x if isinstance(v, str) and v), "기상 위험 낮음")),
                )
            )
            adjusted = adjusted.merge(weather_summary, on="행정동", how="left")
            weather_score = pd.to_numeric(adjusted["weather_risk_score_시나리오"], errors="coerce").fillna(0)
            rain_prob = (
                pd.to_numeric(adjusted["max_rain_probability_시나리오"], errors="coerce").fillna(0)
                if "max_rain_probability_시나리오" in adjusted.columns
                else pd.Series(0, index=adjusted.index)
            )
            rain_score = rain_prob / 100 * 8
            adjustment = (weather_score * 1.4 + rain_score).clip(lower=0, upper=24)
            adjusted["시나리오_보정점수"] = adjustment.round(1)
            adjusted["DLFI_시나리오점수"] = (adjusted["DLFI_기준점수"] + adjustment).round(2)
            adjusted["시나리오_근거"] = (
                "Open-Meteo 7일 예보 기반: 기상위험 "
                + weather_score.round(0).astype(int).astype(str)
                + "점, 최대 강수확률 "
                + rain_prob.round(0).astype(int).astype(str)
                + "%"
            )

    if scenario == "트램 공사 보정":
        if "DLFI_트램동적운영위험도" in adjusted.columns:
            tram_score = pd.to_numeric(adjusted["DLFI_트램동적운영위험도"], errors="coerce")
            adjusted["DLFI_시나리오점수"] = tram_score.fillna(adjusted["DLFI_기준점수"]).round(2)
            adjusted["시나리오_보정점수"] = (adjusted["DLFI_시나리오점수"] - adjusted["DLFI_기준점수"]).round(1)
        elif "tram_dlfi_adjustment" in adjusted.columns:
            adj = pd.to_numeric(adjusted["tram_dlfi_adjustment"], errors="coerce").fillna(0)
            adjusted["시나리오_보정점수"] = adj
            adjusted["DLFI_시나리오점수"] = (adjusted["DLFI_기준점수"] + adj).round(2)
        if "트램위험요약" in adjusted.columns:
            adjusted["시나리오_근거"] = adjusted["트램위험요약"].fillna("트램 공사 영향 데이터 반영")
        elif "tram_event_risk_grade" in adjusted.columns:
            adjusted["시나리오_근거"] = "트램 공사 위험등급 " + adjusted["tram_event_risk_grade"].fillna("확인필요").astype(str)
        else:
            adjusted["시나리오_근거"] = "트램 공사 영향 데이터 반영"

    adjusted["시나리오_순위"] = adjusted["DLFI_시나리오점수"].rank(method="min", ascending=False).astype(int)
    return adjusted


def _filter_master(master: pd.DataFrame, chip: str) -> pd.DataFrame:
    if master.empty:
        return master
    score_col = "DLFI_시나리오점수" if "DLFI_시나리오점수" in master.columns else "DLFI_최종점수"
    score = pd.to_numeric(master[score_col], errors="coerce").fillna(0)
    if chip == "위험만":
        return master[score >= score.quantile(0.75)]
    if chip == "주의만":
        return master[(score >= score.quantile(0.45)) & (score < score.quantile(0.75))]
    if chip == "양호만":
        return master[score < score.quantile(0.45)]
    if chip == "물류 혼잡" and "배송수요점수_최종" in master.columns:
        return master.sort_values("배송수요점수_최종", ascending=False).head(24)
    if chip == "공사 영향":
        col = first_existing(master, ["트램공사_영향점수", "tram_event_risk_score", "tram_risk_score"])
        return master.sort_values(col, ascending=False).head(24) if col else master
    if chip == "기상 영향":
        col = first_existing(master, ["weather_risk_score_시나리오", "weather_risk_score"])
        return master.sort_values(col, ascending=False).head(24) if col else master.sort_values(score_col, ascending=False).head(24)
    return master


def render_daejeon_board_map(rows: pd.DataFrame, selected_dong: str, scenario: str) -> None:
    gu_order = ["유성구", "대덕구", "서구", "중구", "동구"]
    gu_class = {"유성구": "gu-yuseong", "대덕구": "gu-daedeok", "서구": "gu-seo", "중구": "gu-jung", "동구": "gu-dong"}
    score_col = "DLFI_시나리오점수" if "DLFI_시나리오점수" in rows.columns else "DLFI_최종점수"
    gu_ranges = {
        "유성구": (12, 41, 18, 45),
        "대덕구": (50, 83, 18, 45),
        "서구": (13, 40, 56, 82),
        "중구": (45, 60, 55, 74),
        "동구": (62, 86, 55, 84),
    }
    gu_seen: dict[str, int] = {}
    markers = []
    for idx, (_, row) in enumerate(rows.iterrows()):
        gu = row.get("시군구", "")
        score = _score(row, score_col)
        level, tone = _risk_level(score)
        slot = gu_seen.get(gu, 0)
        gu_seen[gu] = slot + 1
        x1, x2, y1, y2 = gu_ranges.get(gu, (18, 82, 20, 82))
        x = x1 + ((slot * 11 + idx * 3) % max(1, x2 - x1))
        y = y1 + ((slot * 13 + idx * 5) % max(1, y2 - y1))
        active = " active" if row.get("행정동", "") == selected_dong else ""
        markers.append(
            f"<span class='dc-pin {tone}{active}' style='left:{x}%; top:{y}%;' title='{row.get('행정동', '')}'>"
            f"<i></i><b>{row.get('행정동', '')}</b></span>"
        )

    gu_cards = []
    for gu in gu_order:
        gdf = rows[rows["시군구"] == gu]
        avg = safe_float(pd.to_numeric(gdf.get(score_col, pd.Series(dtype=float)), errors="coerce").mean(), 0)
        gu_cards.append(
            f"<div class='dc-gu {gu_class[gu]}'><strong>{gu}</strong><span>평균 DLFI {avg:.0f}</span></div>"
        )
    html = (
        "<div class='dc-map-card'>"
        "<div class='dc-map-grid'></div>"
        f"<div class='dc-scenario-badge'>{scenario}</div>"
        f"{''.join(gu_cards)}"
        f"{''.join(markers)}"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_dong_detail_panel(row: pd.Series, scenario: str) -> None:
    score = _score(row, "DLFI_시나리오점수", _score(row, "DLFI_최종점수"))
    base_score = _score(row, "DLFI_기준점수", _score(row, "DLFI_최종점수"))
    adjustment = _score(row, "시나리오_보정점수", 0)
    prob = _score(row, "고위험예측확률") * 100
    level, tone = _risk_level(score)
    policy = row.get("추천정책_텍스트", "탄력 하역권 운영 및 배송 분산 권고")
    rank_value = _score(row, "시나리오_순위", _score(row, "순위", 0))
    rank = int(rank_value) if not math.isnan(rank_value) else "-"
    top_factors = _top_factors(row)
    bars = "".join(_bar(label, value) for label, value in [(c, _score(row, c)) for c in SCORE_COLS if c in row.index])
    factors_html = "".join(
        "<div class='dc-factor'>"
        f"<span>{i}</span><b>{label}</b><i>+{value:.0f}%</i>"
        "</div>"
        for i, (label, value) in enumerate(top_factors, 1)
    )
    html = (
        "<aside class='dc-detail-card'>"
        "<div class='dc-row-between'>"
        f"<span class='dc-code'>DAE-{rank:02d}</span>"
        f"<span class='dc-badge {tone}'>{level}</span>"
        "</div>"
        f"<h2>{row.get('행정동', '-')}</h2>"
        f"<p>{row.get('시군구', '-')} · {row.get('위험유형', '복합 위험형')}</p>"
        "<div class='dc-metric-grid'>"
        f"<div><span>DLFI 점수</span><b>{score:.0f}</b><small>기준 {base_score:.0f} / 보정 {adjustment:+.1f}</small><em></em></div>"
        f"<div><span>예측 확률</span><b>{prob:.1f}%</b><small>{row.get('예측일치', '검증')}</small></div>"
        "</div>"
        f"<div class='dc-scenario-note'><b>{scenario}</b><span>{row.get('시나리오_근거', '통합 데이터 기준 DLFI')}</span></div>"
        "<div class='dc-policy-strip'>"
        f"<span>우선순위</span><b>{row.get('우선순위등급', '-')}</b>"
        f"<span>추천 정책</span><b>{policy}</b>"
        "</div>"
        "<h3>주요 위험 요인 TOP3</h3>"
        f"{factors_html}"
        "<h3>세부 점수 분석</h3>"
        f"<div class='dc-bars'>{bars}</div>"
        "<div class='dc-warning'>"
        "<b>운영 권고사항</b>"
        f"<p>{scenario} 기준으로 하역면 임시 확보, 혼잡 시간대 회피, 보호구역 접근 감속 안내를 함께 적용합니다.</p>"
        "</div>"
        "</aside>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_policy_report(master: pd.DataFrame, data: dict[str, pd.DataFrame], scenario: str) -> None:
    scenario_master = apply_scenario_adjustment(master, data, scenario)
    top = _top_rows(scenario_master, 5)
    top_name = top.iloc[0]["행정동"] if not top.empty else "고위험 행정동"
    gu_focus = top.iloc[0]["시군구"] if not top.empty else "대전"
    avg_delta = 4.2 if scenario == "통합 데이터 기준" else 6.8
    st.markdown(
        f"""
        <section class="dc-report-card">
          <div class="dc-row-between">
            <div>
              <span class="dc-report-icon">AI</span>
              <h2>이번 주 AI 리포트</h2>
            </div>
            <span class="dc-chip-muted">업데이트 2026.07.25 16:00</span>
          </div>
          <p>
            이번 주 {gu_focus} 권역의 고위험 행정동에서 DLFI가 평균 {avg_delta:.1f}점 상승했습니다.
            특히 {top_name}은 보행충돌·단속반복·하역공간 부족이 동시에 높아
            시간제 하역권과 배송 분산 운영을 병행하는 것이 적합합니다.
          </p>
          <div class="dc-insight-grid">
            <span>{top_name} 정차 신고 전주 대비 +34%</span>
            <span>학원·상권 시간대 보행충돌 지수 상승</span>
            <span>트램·기상 보정 시 우선순위 재산정 필요</span>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<h2 class='dc-section-title'>정책 우선순위 TOP 5</h2>", unsafe_allow_html=True)
    policies = _policy_cards(top)
    cols = st.columns(2, gap="large")
    for idx, card in enumerate(policies):
        with cols[idx % 2]:
            render_policy_card(card, idx + 1)


def _policy_cards(top: pd.DataFrame) -> list[dict[str, str]]:
    names = top["행정동"].tolist() if not top.empty else ["온천1동", "둔산2동", "관평동", "노은1동", "오정동"]
    templates = [
        ("하역베이 신설", "긴급", "-18", "약 1.2억", "3개월"),
        ("정차 시간제한 운영", "높음", "-12", "약 0.3억", "1개월"),
        ("대형차 전용 진입로", "중간", "-8", "약 2.4억", "6개월"),
        ("생활물류 앱 하역 예약제", "중간", "-6", "약 0.8억", "4개월"),
        ("기사 현장 안내 표지·알림", "보통", "-4", "약 0.1억", "2주"),
    ]
    return [
        {
            "dong": names[i % len(names)],
            "title": f"{names[i % len(names)]} {title}",
            "level": level,
            "effect": effect,
            "budget": budget,
            "period": period,
        }
        for i, (title, level, effect, budget, period) in enumerate(templates)
    ]


def render_policy_card(card: dict[str, str], index: int) -> None:
    tone = "danger" if card["level"] == "긴급" else "warn" if card["level"] == "높음" else "mid"
    st.markdown(
        f"""
        <article class="dc-policy-card">
          <div class="dc-row-between"><span>P-{index:02d} <i class="dc-badge {tone}">{card['level']}</i></span><small>{card['period']}</small></div>
          <h3>{card['title']}</h3>
          <div class="dc-policy-metrics">
            <div><span>예상 효과</span><b>예상 DLFI {card['effect']}</b></div>
            <div><span>예상 예산</span><b>{card['budget']}</b></div>
          </div>
          <div class="dc-card-actions"><button>상세 보기</button><button class="primary">정책 채택</button></div>
        </article>
        """,
        unsafe_allow_html=True,
    )


def render_data_model_status(master: pd.DataFrame, data: dict[str, pd.DataFrame], scenario: str) -> None:
    accuracy = safe_float(master.get("공식모델_Accuracy", pd.Series([0.892])).mean(), 0.892)
    rows = [
        ("DLFI 예측 모델 v2.4", "정상", f"{accuracy:.3f}", "07.25 15:40", "재실행"),
        ("SHAP 해석 모듈", "정상", "-", "07.25 15:45", "재실행"),
        ("폭염·기상 연동 파이프라인", "정상", "-", "07.25 15:48", "재실행"),
        ("택배 물동량 수집기", "지연", "-", "07.25 14:12", "재실행"),
        ("트램 공사 이벤트 보정", "정상", "-", "07.25 15:50", "재실행"),
    ]
    status_html = "".join(
        f"""
        <tr>
          <td><b>{name}</b></td>
          <td><span class="dc-status {'ok' if status == '정상' else 'delay'}">{status}</span></td>
          <td>{acc}</td>
          <td>{run}</td>
          <td><button class="dc-link-button">{action}</button></td>
        </tr>
        """
        for name, status, acc, run, action in rows
    )
    st.markdown(
        f"""
        <section class="dc-table-card">
          <h2>데이터 · 모델 상태</h2>
          <p>파이프라인·모델 최근 실행 상태</p>
          <table class="dc-status-table">
            <thead><tr><th>구성요소</th><th>상태</th><th>정확도</th><th>최근 실행</th><th>작업</th></tr></thead>
            <tbody>{status_html}</tbody>
          </table>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_user_admin() -> None:
    st.markdown(
        """
        <section class="dc-table-card">
          <h2>사용자 권한 관리</h2>
          <p>발표용 데모 계정별 접근 가능 화면입니다.</p>
          <table class="dc-status-table">
            <thead><tr><th>역할</th><th>접근 화면</th><th>권한 수준</th></tr></thead>
            <tbody>
              <tr><td><b>지자체 관리자</b></td><td>전체 지도, 정책 리포트, 시뮬레이터, 데이터 상태, 날씨</td><td><span class="dc-status ok">관리</span></td></tr>
              <tr><td><b>물류기업</b></td><td>운영지원, 정책 리포트, 날씨, 모델 설명</td><td><span class="dc-status ok">운영</span></td></tr>
              <tr><td><b>배송기사</b></td><td>현장지원, 날씨 주의, 피드백</td><td><span class="dc-status delay">현장</span></td></tr>
              <tr><td><b>분석가/관리자</b></td><td>전체 화면</td><td><span class="dc-status ok">전체</span></td></tr>
            </tbody>
          </table>
        </section>
        """,
        unsafe_allow_html=True,
    )
