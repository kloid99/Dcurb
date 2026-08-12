from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st


APP_DIR = Path(__file__).resolve().parents[1]
LOGIN_BG = APP_DIR / "assets" / "daejeon_login.png"

ROLE_CONFIG = {
    "지자체": {
        "password": "dcurb2026",
        "tabs": ["municipality", "simulator", "weather", "model"],
        "label": "지자체 정책 담당자",
    },
    "물류기업": {
        "password": "logi2026",
        "tabs": ["logistics", "simulator", "weather", "model"],
        "label": "물류기업 운영 담당자",
    },
    "배송기사": {
        "password": "driver2026",
        "tabs": ["driver"],
        "label": "배송기사 현장 사용자",
    },
    "분석가/관리자": {
        "password": "admin2026",
        "tabs": ["municipality", "simulator", "logistics", "driver", "weather", "model"],
        "label": "분석가/관리자",
    },
}


def image_to_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def inject_login_css() -> None:
    bg = image_to_data_uri(LOGIN_BG)
    background = f"url('{bg}')" if bg else "linear-gradient(135deg, #0f172a, #1d4ed8)"
    st.markdown(
        f"""
        <style>
        .stApp {{
            background:
                linear-gradient(90deg, rgba(2, 6, 23, .82), rgba(15, 23, 42, .45)),
                {background};
            background-size: cover;
            background-position: center;
        }}
        .block-container {{
            max-width: 1180px;
            padding-top: 5rem;
        }}
        .login-copy {{
            color: white;
            padding: 26px 0 0;
        }}
        .login-kicker {{
            font-size: 13px;
            font-weight: 900;
            opacity: .84;
            margin: 0 0 10px;
        }}
        .login-title {{
            font-size: 46px;
            line-height: 1.1;
            font-weight: 950;
            margin: 0;
            letter-spacing: 0;
        }}
        .login-sub {{
            max-width: 580px;
            margin-top: 16px;
            font-size: 16px;
            line-height: 1.7;
            color: rgba(255,255,255,.84);
        }}
        [data-testid="stForm"] {{
            border: 1px solid rgba(255,255,255,.24);
            border-radius: 20px;
            padding: 26px;
            background: rgba(255,255,255,.92);
            box-shadow: 0 24px 60px rgba(0,0,0,.28);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_login() -> bool:
    if st.session_state.get("authenticated"):
        return True

    inject_login_css()
    left, right = st.columns([1.25, 0.75], gap="large")
    with left:
        st.markdown(
            """
            <section class="login-copy">
              <p class="login-kicker">DAEJEON LAST-MILE LOGISTICS DECISION DASHBOARD</p>
              <h1 class="login-title">D-Curb Guardian</h1>
              <p class="login-sub">
                사용자 역할에 따라 지자체 정책지원, 물류기업 운영지원, 배송기사 현장지원 화면을 다르게 제공합니다.
                로그인 후 필요한 기능만 빠르게 접근할 수 있습니다.
              </p>
            </section>
            """,
            unsafe_allow_html=True,
        )

    with right:
        with st.form("login_form"):
            st.subheader("로그인")
            role = st.selectbox("사용자 유형", list(ROLE_CONFIG.keys()))
            username = st.text_input("사용자명", value="demo")
            password = st.text_input("비밀번호", type="password")
            submitted = st.form_submit_button("대시보드 시작", width="stretch")
            if submitted:
                if password == ROLE_CONFIG[role]["password"]:
                    st.session_state["authenticated"] = True
                    st.session_state["role"] = role
                    st.session_state["username"] = username
                    st.rerun()
                else:
                    st.error("비밀번호가 맞지 않습니다.")

        st.caption("데모 비밀번호: 지자체 dcurb2026 / 물류기업 logi2026 / 배송기사 driver2026 / 관리자 admin2026")
    return False


def current_role() -> str:
    return st.session_state.get("role", "지자체")


def allowed_tabs() -> list[str]:
    return ROLE_CONFIG[current_role()]["tabs"]


def logout_button() -> None:
    role = current_role()
    cols = st.columns([0.75, 0.25])
    cols[0].caption(f"{ROLE_CONFIG[role]['label']} · {st.session_state.get('username', 'demo')}님 접속 중")
    if cols[1].button("로그아웃"):
        st.session_state.clear()
        st.rerun()
