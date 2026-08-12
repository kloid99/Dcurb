from __future__ import annotations

import streamlit as st

from modules.auth import ROLE_CONFIG, current_role, render_login
from modules.load_data import load_data, prepare_master
from views.driver_view import render_driver_view
from views.logistics_view import render_logistics_view
from views.model_explain_view import render_model_explain_view
from views.platform_views import (
    render_data_model_status,
    render_dcurb_sidebar,
    render_overview_map,
    render_policy_report,
    render_topbar,
    render_user_admin,
)
from views.simulator_view import render_simulator_view
from views.weather_view import render_weather_view


st.set_page_config(
    page_title="D-Curb Guardian",
    page_icon="D",
    layout="wide",
)


MENU_META = {
    "전체 DLFI 지도": {
        "key": "municipality",
        "title": "대전 전체 DLFI 지도",
        "subtitle": "보행 혼잡, 배송 동선, 공사, 기상 데이터를 결합해 행정동별 물류-보행 간섭 위험도를 표시합니다.",
    },
    "정책 추천 · AI 리포트": {
        "key": "municipality",
        "title": "정책 추천 · AI 리포트",
        "subtitle": "고위험 행정동의 원인과 실행 가능한 정책 패키지를 우선순위로 정리합니다.",
    },
    "데이터 · 모델 상태": {
        "key": "model",
        "title": "데이터 · 모델 상태",
        "subtitle": "전처리 파이프라인, 예측 모델, 외부 이벤트 연동 상태를 점검합니다.",
    },
    "사용자 권한 관리": {
        "key": "model",
        "title": "사용자 권한 관리",
        "subtitle": "사용자 유형별 접근 권한과 발표용 데모 계정을 관리합니다.",
    },
    "정책 시뮬레이터": {
        "key": "simulator",
        "title": "정책 시뮬레이터",
        "subtitle": "하역면 수, 배송 분산율, 기상·트램 시나리오를 바꿔 적용 전후 DLFI를 비교합니다.",
    },
    "물류기업 운영지원": {
        "key": "logistics",
        "title": "물류기업 운영지원",
        "subtitle": "시간대별 배송 집중도와 혼잡도를 기반으로 분산 배송 권장 시간대를 제시합니다.",
    },
    "배송기사 현장지원": {
        "key": "driver",
        "title": "배송기사 현장지원",
        "subtitle": "현장 위치별 추천 하역시간, 주의 요인, 기사 안내문구와 피드백 입력을 제공합니다.",
    },
    "날씨 리스크": {
        "key": "weather",
        "title": "날씨 리스크",
        "subtitle": "Open-Meteo 7일 예보를 행정동·시간대 기준으로 집계해 배송 위험 시점을 분리합니다.",
    },
    "데이터 · 모델 설명": {
        "key": "model",
        "title": "데이터 · 모델 설명",
        "subtitle": "DLFI 산식, 변수 중요도, 군집 유형, 신뢰도 산정 방식과 한계를 설명합니다.",
    },
}


ROLE_MENUS = {
    "지자체": ["전체 DLFI 지도", "정책 추천 · AI 리포트", "데이터 · 모델 상태", "사용자 권한 관리", "정책 시뮬레이터", "날씨 리스크"],
    "물류기업": ["물류기업 운영지원", "정책 추천 · AI 리포트", "정책 시뮬레이터", "날씨 리스크", "데이터 · 모델 설명"],
    "배송기사": ["배송기사 현장지원", "날씨 리스크"],
    "분석가/관리자": [
        "전체 DLFI 지도",
        "정책 추천 · AI 리포트",
        "데이터 · 모델 상태",
        "사용자 권한 관리",
        "정책 시뮬레이터",
        "물류기업 운영지원",
        "배송기사 현장지원",
        "날씨 리스크",
        "데이터 · 모델 설명",
    ],
}


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --dc-bg: #f6f8fb;
            --dc-card: #ffffff;
            --dc-ink: #0f172a;
            --dc-muted: #72819a;
            --dc-line: #e4ebf3;
            --dc-teal: #0f9f8f;
            --dc-teal-dark: #08796e;
            --dc-mint: #e9fbf6;
            --dc-red: #ef476f;
            --dc-orange: #f59e0b;
            --dc-blue: #334155;
        }
        .stApp { background: var(--dc-bg); color: var(--dc-ink); }
        .block-container {
            max-width: none;
            padding: 1.9rem 1.4rem 1rem 1.4rem;
        }
        section[data-testid="stSidebar"] {
            width: 282px !important;
            background: #ffffff;
            border-right: 1px solid var(--dc-line);
        }
        section[data-testid="stSidebar"] > div { padding: 1.15rem .75rem; }
        section[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] {
            gap: .25rem;
        }
        section[data-testid="stSidebar"] [data-testid="stRadio"] > label {
            display: none;
        }
        section[data-testid="stSidebar"] [data-testid="stRadio"] label {
            display: flex;
            align-items: center;
            min-height: 44px;
            padding: .6rem .7rem;
            border-radius: 10px;
            color: #56657a;
            font-weight: 760;
            width: 100%;
            margin: .12rem 0;
            cursor: pointer;
        }
        section[data-testid="stSidebar"] [data-testid="stRadio"] input[type="radio"] {
            display: none;
        }
        section[data-testid="stSidebar"] [data-testid="stRadio"] label > div:first-child {
            display: none;
        }
        section[data-testid="stSidebar"] [data-testid="stRadio"] label p {
            font-size: 15px;
            line-height: 1.2;
            white-space: nowrap;
        }
        section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
            background: var(--dc-mint);
            color: var(--dc-teal-dark);
        }
        section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) p {
            color: var(--dc-teal-dark);
            font-weight: 900;
        }
        .dc-brand {
            display: flex;
            align-items: center;
            gap: .8rem;
            padding: .25rem .55rem 1.2rem;
            border-bottom: 1px solid var(--dc-line);
            margin-bottom: 1.3rem;
        }
        .dc-logo {
            width: 42px;
            height: 42px;
            display: grid;
            place-items: center;
            border-radius: 10px;
            background: #16c7a8;
            color: white;
            font-weight: 950;
        }
        .dc-brand b { display: block; font-size: 17px; line-height: 1.05; }
        .dc-brand span { color: #718096; font-size: 13px; }
        .dc-menu-label {
            color: #a2aec1;
            font-size: 12px;
            font-weight: 900;
            padding: .35rem .7rem;
        }
        .dc-spacer { margin-top: .75rem; border-top: 1px solid var(--dc-line); padding-top: .9rem; }
        .dc-sidebar-fill { min-height: 330px; }
        .dc-user-card {
            display: flex;
            align-items: center;
            gap: .75rem;
            padding: .8rem;
            border-top: 1px solid var(--dc-line);
            margin-top: 1rem;
        }
        .dc-avatar {
            width: 42px;
            height: 42px;
            border-radius: 999px;
            display: grid;
            place-items: center;
            background: #c5fff3;
            color: var(--dc-teal-dark);
            font-weight: 900;
        }
        .dc-user-card b { display:block; font-size: 15px; }
        .dc-user-card span { color: #7b8aa0; font-size: 12px; }
        .dc-topbar {
            min-height: 68px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: .95rem 1.25rem;
            margin: 0 -1.4rem 1.45rem;
            border-bottom: 1px solid var(--dc-line);
            background: #ffffff;
        }
        .dc-topbar h1 {
            margin: 0;
            font-size: 18px;
            line-height: 1.3;
            letter-spacing: 0;
        }
        .dc-topbar p {
            margin: .22rem 0 0;
            color: #76869d;
            font-size: 13px;
        }
        .dc-top-actions { display: flex; align-items: center; gap: .75rem; }
        .dc-chip-muted, .dc-role-chip {
            display: inline-flex;
            align-items: center;
            border: 1px solid var(--dc-line);
            border-radius: 9px;
            padding: .45rem .75rem;
            color: #73849b;
            font-size: 13px;
            background: #fbfdff;
            white-space: nowrap;
        }
        .dc-role-chip {
            border-color: #b7f1e6;
            color: var(--dc-teal-dark);
            background: #effffb;
            border-radius: 999px;
            font-weight: 800;
        }
        div[role="radiogroup"][aria-label="지도 필터"] {
            display: flex;
            gap: .45rem;
            margin-bottom: 1.2rem;
        }
        div[role="radiogroup"][aria-label="지도 필터"] label {
            display: inline-flex;
            align-items: center;
            border: 1px solid var(--dc-line);
            border-radius: 999px;
            background: #fff;
            padding: .48rem .85rem;
            font-weight: 800;
            color: #72819a;
        }
        div[role="radiogroup"][aria-label="지도 필터"] label > div:first-child {
            display: none;
        }
        div[role="radiogroup"][aria-label="지도 필터"] label p {
            color: inherit;
            font-weight: 850;
            white-space: nowrap;
        }
        div[role="radiogroup"][aria-label="지도 필터"] label:has(input:checked) {
            background: var(--dc-teal);
            color: white;
            border-color: var(--dc-teal);
        }
        .dc-map-card {
            position: relative;
            min-height: 640px;
            border: 1px solid var(--dc-line);
            border-radius: 14px;
            overflow: hidden;
            background: #f8fbff;
            box-shadow: 0 10px 26px rgba(15, 23, 42, .045);
        }
        .dc-map-grid {
            position: absolute;
            inset: 0;
            background-image:
              linear-gradient(#eaf0f6 1px, transparent 1px),
              linear-gradient(90deg, #eaf0f6 1px, transparent 1px);
            background-size: 60px 60px;
            opacity: .92;
        }
        .dc-scenario-badge {
            position: absolute;
            left: 18px;
            top: 18px;
            z-index: 3;
            padding: .42rem .68rem;
            border-radius: 999px;
            border: 1px solid #d8efe9;
            color: var(--dc-teal-dark);
            background: rgba(255,255,255,.9);
            font-size: 12px;
            font-weight: 900;
        }
        .dc-gu {
            position: absolute;
            border: 4px solid rgba(15,159,143,.25);
            box-shadow: 0 8px 22px rgba(15, 23, 42, .08);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            color: #344054;
            z-index: 1;
        }
        .dc-gu strong { font-size: 31px; letter-spacing: 0; }
        .dc-gu span { margin-top: .2rem; font-size: 12px; color: #6c7b90; font-weight: 800; }
        .gu-yuseong { left: 6%; top: 9%; width: 39%; height: 40%; background: #cef8dc; clip-path: polygon(4% 4%, 100% 4%, 95% 78%, 60% 92%, 10% 88%); }
        .gu-daedeok { left: 45%; top: 8%; width: 43%; height: 43%; background: #cdf9df; clip-path: polygon(0 3%, 97% 0, 100% 72%, 82% 96%, 25% 98%, 5% 78%); border-color: #11b889; }
        .gu-seo { left: 8%; top: 48%; width: 38%; height: 39%; background: #fff4bd; clip-path: polygon(4% 0, 80% 4%, 100% 34%, 86% 91%, 12% 98%, 4% 73%); border-color: #f6d365; }
        .gu-jung { left: 42%; top: 48%; width: 22%; height: 29%; background: #fff3d2; clip-path: polygon(20% 0, 78% 0, 100% 70%, 56% 100%, 0 78%); border-color: #ffd166; }
        .gu-dong { right: 4%; top: 47%; width: 41%; height: 50%; background: #ffdedd; clip-path: polygon(5% 0, 85% 6%, 96% 45%, 100% 100%, 25% 100%, 0 57%); border-color: #f7c6c7; }
        .dc-pin {
            position: absolute;
            transform: translate(-50%, -50%);
            z-index: 5;
            display: inline-flex;
            align-items: center;
            gap: .3rem;
            font-size: 10px;
            font-weight: 900;
            color: #344054;
            padding: .18rem .45rem .18rem .2rem;
            border-radius: 999px;
            background: rgba(255,255,255,.95);
            border: 1px solid #dce6f0;
            box-shadow: 0 8px 18px rgba(15, 23, 42, .12);
        }
        .dc-pin i {
            width: 10px;
            height: 10px;
            display: inline-block;
            border-radius: 999px;
            background: var(--dc-teal);
        }
        .dc-pin.danger i { background: var(--dc-red); }
        .dc-pin.warn i { background: var(--dc-orange); }
        .dc-pin.mid i { background: #ffd166; }
        .dc-pin.active {
            border-color: #7f1d1d;
            transform: translate(-50%, -50%) scale(1.12);
        }
        .dc-pin.active i {
            width: 16px;
            height: 16px;
            background: #7f1d1d;
        }
        .dc-detail-card, .dc-report-card, .dc-table-card, .dc-policy-card {
            border: 1px solid var(--dc-line);
            background: white;
            border-radius: 14px;
            box-shadow: 0 10px 26px rgba(15, 23, 42, .04);
        }
        .dc-detail-card { padding: 1.35rem; min-height: 640px; }
        .dc-row-between { display: flex; align-items: center; justify-content: space-between; gap: .8rem; }
        .dc-code { color: #98a6ba; font-size: 12px; font-weight: 900; }
        .dc-badge {
            display: inline-flex;
            border-radius: 999px;
            padding: .2rem .58rem;
            font-style: normal;
            font-size: 12px;
            font-weight: 900;
            background: #ecfdf5;
            color: var(--dc-teal-dark);
            border: 1px solid #b7f1e6;
        }
        .dc-badge.danger { background: #fff0f3; color: #d92d54; border-color: #ffd1dc; }
        .dc-badge.warn { background: #fff8e7; color: #b77900; border-color: #ffebb0; }
        .dc-badge.mid { background: #edfffb; color: var(--dc-teal-dark); }
        .dc-detail-card h2 { margin: .55rem 0 0; font-size: 23px; }
        .dc-detail-card p { color: #75859b; margin: .35rem 0 1rem; }
        .dc-metric-grid, .dc-policy-metrics {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: .8rem;
            margin: 1.1rem 0;
        }
        .dc-metric-grid div, .dc-policy-metrics div {
            border-radius: 9px;
            padding: .95rem;
            background: #f8fafc;
            border: 1px solid #edf2f7;
        }
        .dc-metric-grid div:first-child { background: #eefdf8; border-color: #caf8e8; }
        .dc-metric-grid span, .dc-policy-metrics span { display:block; color: #76869d; font-size: 12px; font-weight: 900; }
        .dc-metric-grid b, .dc-policy-metrics b { display:block; margin-top:.35rem; font-size: 22px; color: var(--dc-ink); }
        .dc-metric-grid em {
            display:block;
            height: 8px;
            border-radius: 999px;
            margin-top: .7rem;
            background: linear-gradient(90deg, var(--dc-teal), #c6eee8 58%, var(--dc-red));
        }
        .dc-metric-grid small { color: #1faa80; font-weight: 900; }
        .dc-policy-strip {
            display: grid;
            grid-template-columns: .75fr 1fr;
            gap: .65rem;
            padding: .95rem;
            border-radius: 9px;
            background: #f8fafc;
            margin-bottom: 1rem;
        }
        .dc-policy-strip span { color: #76869d; }
        .dc-policy-strip b { color: var(--dc-teal-dark); }
        .dc-scenario-note {
            display: grid;
            gap: .25rem;
            padding: .85rem .95rem;
            border-radius: 9px;
            border: 1px solid #d8efe9;
            background: #f0fffb;
            margin: -.25rem 0 1rem;
        }
        .dc-scenario-note b {
            color: var(--dc-teal-dark);
            font-size: 13px;
        }
        .dc-scenario-note span {
            color: #5d6b80;
            font-size: 12px;
            line-height: 1.45;
        }
        .dc-detail-card h3 { margin: 1rem 0 .65rem; font-size: 14px; color: #667085; }
        .dc-factor { display:grid; grid-template-columns: 28px 1fr 56px; align-items:center; gap:.45rem; margin:.45rem 0; }
        .dc-factor span { width:24px; height:24px; border-radius:999px; display:grid; place-items:center; background:#1f2937; color:white; font-size:12px; font-weight:900; }
        .dc-factor b { font-size: 14px; color:#667085; }
        .dc-factor i { font-style:normal; color:#8da0b6; text-align:right; font-weight:900; }
        .dc-bar-row { display:grid; grid-template-columns: 84px 1fr 38px; gap:.55rem; align-items:center; margin:.44rem 0; font-size:12px; color:#667085; }
        .dc-bar-track { height:18px; border-radius:4px; background:#edf2f7; overflow:hidden; }
        .dc-bar-track i { display:block; height:100%; border-radius:4px; }
        .dc-warning {
            margin-top: 1.25rem;
            padding: 1rem;
            border-radius: 10px;
            border: 1px solid #ffebb0;
            background: #fff8e7;
            color: #a15c07;
        }
        .dc-warning p { margin:.35rem 0 0; color:#b77900; }
        .dc-mini-title, .dc-section-title {
            font-size: 20px;
            font-weight: 950;
            margin: 1.2rem 0 .85rem;
        }
        .dc-report-card { padding: 1.5rem; margin-bottom: 1.45rem; }
        .dc-report-card h2 { display:inline-block; margin:0 0 .7rem .55rem; font-size:23px; }
        .dc-report-card p { color:#4e5d73; line-height:1.7; }
        .dc-report-icon { display:inline-grid; place-items:center; width:36px; height:36px; border-radius:8px; background:var(--dc-mint); color:var(--dc-teal-dark); font-weight:950; }
        .dc-insight-grid { display:grid; grid-template-columns: repeat(3, 1fr); gap:.85rem; margin-top:1.2rem; }
        .dc-insight-grid span {
            padding:.85rem 1rem;
            border-radius:8px;
            background:#f8fafc;
            color:#4c5b70;
            font-weight:800;
        }
        .dc-policy-card { padding: 1.25rem; margin-bottom: 1.25rem; min-height: 235px; }
        .dc-policy-card h3 { margin: 1rem 0; font-size:20px; }
        .dc-card-actions { display:flex; justify-content:flex-end; gap:.55rem; margin-top:1rem; }
        .dc-card-actions button, .dc-link-button {
            border:1px solid var(--dc-line);
            background:white;
            color:#59697f;
            border-radius:8px;
            padding:.45rem .8rem;
            font-weight:800;
        }
        .dc-card-actions .primary {
            background: var(--dc-teal);
            color:white;
            border-color: var(--dc-teal);
        }
        .dc-table-card { padding: 1.5rem; }
        .dc-table-card h2 { margin:0 0 .35rem; font-size:24px; }
        .dc-table-card p { color:#76869d; margin-bottom:1.6rem; }
        .dc-status-table { width:100%; border-collapse: collapse; overflow:hidden; }
        .dc-status-table th {
            text-align:left;
            padding: .9rem 1rem;
            background:#f8fafc;
            color:#7c8ba0;
            font-weight:900;
            font-size:13px;
        }
        .dc-status-table td {
            padding: 1rem;
            border-top: 1px solid #edf2f7;
            color:#526177;
        }
        .dc-status.ok, .dc-status.delay {
            display:inline-flex;
            padding:.18rem .6rem;
            border-radius:999px;
            font-weight:900;
            font-size:12px;
            border:1px solid #b7f1e6;
            color:var(--dc-teal-dark);
            background:#ecfdf5;
        }
        .dc-status.delay { border-color:#ffebb0; color:#b77900; background:#fff8e7; }
        .stButton button {
            border-radius: 8px;
            border: 1px solid var(--dc-line);
            background: white;
            color: #526177;
            font-weight: 850;
        }
        @media (max-width: 1100px) {
            .dc-insight-grid, .dc-metric-grid, .dc-policy-metrics { grid-template-columns: 1fr; }
            .dc-map-card, .dc-detail-card { min-height: 520px; }
            .dc-pin b { display:none; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    if not render_login():
        return

    inject_css()
    data = load_data()
    master = prepare_master(data)
    if master.empty:
        st.error("final_modelling.csv를 찾지 못했습니다. dcurb_dashboard/data 폴더 구성을 확인해 주세요.")
        st.stop()

    role = current_role()
    role_label = ROLE_CONFIG[role]["label"]
    menu_options = ROLE_MENUS.get(role, ROLE_MENUS["지자체"])
    selected_menu, scenario = render_dcurb_sidebar(menu_options, role_label)
    meta = MENU_META[selected_menu]
    render_topbar(meta["title"], meta["subtitle"], role_label)

    if selected_menu == "전체 DLFI 지도":
        render_overview_map(master, data, scenario)
    elif selected_menu == "정책 추천 · AI 리포트":
        render_policy_report(master, data, scenario)
    elif selected_menu == "데이터 · 모델 상태":
        render_data_model_status(master, data, scenario)
    elif selected_menu == "사용자 권한 관리":
        render_user_admin()
    elif selected_menu == "정책 시뮬레이터":
        render_simulator_view(master, data)
    elif selected_menu == "물류기업 운영지원":
        render_logistics_view(master, data)
    elif selected_menu == "배송기사 현장지원":
        render_driver_view(master, data)
    elif selected_menu == "날씨 리스크":
        render_weather_view(master, data)
    elif selected_menu == "데이터 · 모델 설명":
        render_model_explain_view(master, data)

    st.markdown(
        "<p style='color:#b4bfd0; font-size:12px; margin-top:2rem;'>© 2026 D-Curb Guardian · 지자체 관리자 콘솔</p>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
