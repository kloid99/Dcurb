from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from modules.auth import current_role, render_login


st.set_page_config(
    page_title="D-Curb Guardian",
    page_icon="D",
    layout="wide",
    initial_sidebar_state="collapsed",
)


APP_DIR = Path(__file__).resolve().parent
REACT_APP_DIR = APP_DIR.parent / "dcurb_guardian_source"
DIST_DIR = APP_DIR / "react_dist"
INDEX_HTML = DIST_DIR / "index.html"
REACT_DATA_DIR = APP_DIR / "react_data"
WEATHER_TIMEBLOCK_CSV = REACT_DATA_DIR / "daejeon_openmeteo_timeblock_7days.csv"
DONG_GEO_JSON = REACT_DATA_DIR / "dong_geo.json"
REACT_SERVER_URL = os.environ.get("DCURB_REACT_SERVER_URL", "http://localhost:3000")
REACT_HEALTH_URL = f"{REACT_SERVER_URL}/api/health"
WEATHER_SNAPSHOT_JSON = REACT_APP_DIR / "data" / "weather_api_snapshot.json"


def _num(value, default: float = 0.0) -> float:
    parsed = pd.to_numeric(value, errors="coerce")
    if pd.isna(parsed):
        return default
    return float(parsed)


@st.cache_data(show_spinner=False)
def build_weather_payload(weather_mtime: float, geo_mtime: float) -> dict:
    del weather_mtime, geo_mtime
    fallback = {
        "fetchedAt": "2026-07-25T00:00:00+09:00",
        "stale": True,
        "dates": [],
        "timeBlocks": ["07~10", "10~12", "12~14", "14~17", "17~20", "20~23"],
        "byDongCode": {},
    }
    if not WEATHER_TIMEBLOCK_CSV.exists() or not DONG_GEO_JSON.exists():
        fallback["error"] = "Streamlit 내부 날씨 CSV 또는 행정동 GeoJSON을 찾지 못했습니다."
        return fallback

    weather = pd.read_csv(WEATHER_TIMEBLOCK_CSV, encoding="utf-8-sig")
    geo = json.loads(DONG_GEO_JSON.read_text(encoding="utf-8"))
    geo_lookup = {(item["gu"], item["dong"]): item for item in geo.get("dongs", [])}

    dates = sorted(weather["forecast_date"].dropna().astype(str).unique().tolist())
    time_order = ["07~10시", "10~12시", "12~14시", "14~17시", "17~20시", "20~23시"]
    time_blocks = [block.replace("시", "") for block in time_order]
    by_dong_code: dict[str, dict] = {}

    weather = weather.sort_values(["시군구", "행정동", "forecast_date", "time_block"])
    for (gu, dong), group in weather.groupby(["시군구", "행정동"], dropna=False):
        gu = str(gu)
        dong = str(dong)
        geo_item = geo_lookup.get((gu, dong))
        if not geo_item:
            continue

        dong_code = str(geo_item["dongCode"])
        forecast: dict[str, dict] = {}
        for _, row in group.iterrows():
            date = str(row["forecast_date"])
            block = str(row["time_block"]).replace("시", "")
            forecast.setdefault(date, {})[block] = {
                "score": _num(row.get("weather_risk_score", 0)),
                "status": str(row.get("delivery_status", "정상 운영")),
                "reason": str(row.get("weather_risk_reason", "기상 위험 낮음")),
                "maxRainProb": _num(row.get("max_rain_probability", 0)),
                "maxPrecipMm": _num(row.get("max_hourly_precipitation_mm", 0)),
                "maxTempC": _num(row.get("max_temperature", 0)),
            }

        by_dong_code[dong_code] = {
            "dongCode": dong_code,
            "dong": dong,
            "gu": gu,
            "gridId": str(geo_item.get("gridId", "")),
            "forecast": forecast,
        }

    return {
        "fetchedAt": "2026-07-25T00:00:00+09:00",
        "stale": False,
        "source": "final-20260725T063735Z-1-001.zip / daejeon_openmeteo_timeblock_7days.csv",
        "dates": dates,
        "timeBlocks": time_blocks,
        "byDongCode": by_dong_code,
    }


def _react_role_payload() -> tuple[str, list[str]]:
    role = current_role()
    if role == "분석가/관리자":
        return role, ["지자체", "물류기업", "배송기사"]
    if role in {"지자체", "물류기업", "배송기사"}:
        return role, [role]
    return "지자체", ["지자체"]


def _server_is_ready(timeout: float = 0.35) -> bool:
    try:
        with urlopen(REACT_HEALTH_URL, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False


def ensure_weather_snapshot() -> None:
    if not WEATHER_TIMEBLOCK_CSV.exists() or not DONG_GEO_JSON.exists():
        return

    source_mtime = max(WEATHER_TIMEBLOCK_CSV.stat().st_mtime, DONG_GEO_JSON.stat().st_mtime)
    if WEATHER_SNAPSHOT_JSON.exists() and WEATHER_SNAPSHOT_JSON.stat().st_mtime >= source_mtime:
        return

    WEATHER_SNAPSHOT_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = build_weather_payload(WEATHER_TIMEBLOCK_CSV.stat().st_mtime, DONG_GEO_JSON.stat().st_mtime)
    WEATHER_SNAPSHOT_JSON.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


@st.cache_resource(show_spinner=False)
def start_react_server() -> dict:
    if _server_is_ready():
        return {"ok": True, "mode": "existing"}

    server_entry = REACT_APP_DIR / "dist" / "server.cjs"
    if not server_entry.exists():
        return {
            "ok": False,
            "error": "React build is missing. Run npm run build in dcurb_guardian_source.",
        }

    env = os.environ.copy()
    env["NODE_ENV"] = "production"
    env.setdefault("PORT", "3000")

    creationflags = 0
    if sys.platform.startswith("win"):
        creationflags = subprocess.CREATE_NO_WINDOW

    process = subprocess.Popen(
        ["node", str(server_entry)],
        cwd=str(REACT_APP_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )

    for _ in range(28):
        if _server_is_ready(timeout=0.2):
            return {"ok": True, "mode": "started", "pid": process.pid}
        if process.poll() is not None:
            return {"ok": False, "error": "React server exited before becoming ready."}
        time.sleep(0.18)

    return {"ok": False, "error": "React server did not respond on port 3000."}


def _request_host() -> str:
    context = getattr(st, "context", None)
    headers = getattr(context, "headers", None)
    if headers:
        try:
            return headers.get("host", "")
        except Exception:
            return ""
    return ""


def _browser_react_server_url() -> str:
    host = _request_host()
    if not host:
        return REACT_SERVER_URL

    hostname = host.split(":")[0]
    scheme = "http"
    if hostname in {"localhost", "127.0.0.1", "::1"}:
        return REACT_SERVER_URL
    return f"{scheme}://{hostname}:3000"


def _streamlit_return_url() -> str:
    host = _request_host()
    if not host:
        return "http://localhost:8501/?logout=1"
    return f"http://{host}/?logout=1"


def react_dashboard_url() -> str:
    role, allowed_roles = _react_role_payload()
    allowed = ",".join(allowed_roles)
    return_to = _streamlit_return_url()
    return f"{_browser_react_server_url()}/?role={quote(role)}&allowed={quote(allowed)}&returnTo={quote(return_to, safe='')}"


def inline_vite_build(index_html: str, weather_payload: dict) -> str:
    html = index_html
    weather_json = json.dumps(weather_payload, ensure_ascii=False).replace("</script", "<\\/script")
    react_role, allowed_roles = _react_role_payload()
    role_json = json.dumps(react_role, ensure_ascii=False)
    allowed_roles_json = json.dumps(allowed_roles, ensure_ascii=False)
    weather_bridge = f"""
        <script>
          window.__DCURB_WEATHER__ = {weather_json};
          window.__DCURB_ROLE__ = {role_json};
          window.__DCURB_ALLOWED_ROLES__ = {allowed_roles_json};
          window.__DCURB_ORIGINAL_FETCH__ = window.fetch ? window.fetch.bind(window) : null;
          window.fetch = function(input, init) {{
            const url = typeof input === 'string' ? input : (input && input.url ? input.url : '');
            if (url.includes('/api/weather')) {{
              return Promise.resolve(new Response(JSON.stringify(window.__DCURB_WEATHER__), {{
                status: 200,
                headers: {{ 'Content-Type': 'application/json' }}
              }}));
            }}
            return window.__DCURB_ORIGINAL_FETCH__(input, init);
          }};
        </script>
    """
    loading_shell = """
    <div id="root">
      <div class="dc-loading-shell">
        <aside class="dc-loading-side">
          <div class="dc-loading-logo">D</div>
          <div>
            <b>D-Curb Guardian</b>
            <span>권한 확인 및 데이터 연결 중</span>
          </div>
        </aside>
        <main class="dc-loading-main">
          <div class="dc-loading-top">
            <div>
              <strong>대시보드 준비 중</strong>
              <span>DLFI, 트램, 기상 데이터를 불러오고 있습니다.</span>
            </div>
            <i></i>
          </div>
          <div class="dc-loading-grid">
            <section></section><section></section><section></section><section></section>
          </div>
          <div class="dc-loading-card"></div>
        </main>
      </div>
    </div>
    """
    html = re.sub(r'<div id="root"></div>', loading_shell, html, count=1)

    css_links = re.findall(r'<link[^>]+href="([^"]+\.css)"[^>]*>', html)
    for href in css_links:
        css_path = DIST_DIR / href.lstrip("/")
        if css_path.exists():
            css = css_path.read_text(encoding="utf-8")
            html = re.sub(
                rf'<link[^>]+href="{re.escape(href)}"[^>]*>',
                lambda _: f"<style>{css}</style>",
                html,
                count=1,
            )

    module_scripts = re.findall(r'<script[^>]+type="module"[^>]+src="([^"]+\.js)"[^>]*></script>', html)
    for src in module_scripts:
        js_path = DIST_DIR / src.lstrip("/")
        if js_path.exists():
            js = js_path.read_text(encoding="utf-8")
            html = re.sub(
                rf'<script[^>]+type="module"[^>]+src="{re.escape(src)}"[^>]*></script>',
                lambda _: f"<script type='module'>{js}</script>",
                html,
                count=1,
            )

    return html.replace(
        "</head>",
        weather_bridge
        + """
        <style>
          html, body, #root {
            width: 100%;
            min-height: 100vh;
            margin: 0;
            overflow-x: hidden;
          }
          body {
            background: #f6f8fb;
          }
          .dc-loading-shell {
            min-height: 100vh;
            display: grid;
            grid-template-columns: 260px 1fr;
            background: #f6f8fb;
            color: #0f172a;
          }
          .dc-loading-side {
            background: #0f172a;
            color: white;
            padding: 26px 22px;
            display: flex;
            gap: 12px;
            align-items: flex-start;
          }
          .dc-loading-logo {
            width: 40px;
            height: 40px;
            border-radius: 12px;
            background: #14b8a6;
            display: grid;
            place-items: center;
            font-weight: 900;
          }
          .dc-loading-side b { display:block; font-size:16px; }
          .dc-loading-side span { display:block; margin-top:5px; color:#94a3b8; font-size:12px; }
          .dc-loading-main { padding: 28px; }
          .dc-loading-top {
            height: 76px;
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 16px;
            padding: 16px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 10px 28px rgba(15,23,42,.04);
          }
          .dc-loading-top strong { display:block; font-size:18px; }
          .dc-loading-top span { display:block; margin-top:4px; font-size:13px; color:#64748b; }
          .dc-loading-top i {
            width: 24px;
            height: 24px;
            border-radius: 999px;
            border: 3px solid #ccfbf1;
            border-top-color: #0f766e;
            animation: dc-spin .8s linear infinite;
          }
          .dc-loading-grid {
            display:grid;
            grid-template-columns: repeat(4, 1fr);
            gap:14px;
            margin-top:18px;
          }
          .dc-loading-grid section,
          .dc-loading-card {
            position:relative;
            overflow:hidden;
            background:#fff;
            border:1px solid #e2e8f0;
            border-radius:16px;
            box-shadow: 0 10px 28px rgba(15,23,42,.04);
          }
          .dc-loading-grid section { height:96px; }
          .dc-loading-card { height:520px; margin-top:18px; }
          .dc-loading-grid section::after,
          .dc-loading-card::after {
            content:"";
            position:absolute;
            inset:0;
            transform:translateX(-100%);
            background: linear-gradient(90deg, transparent, rgba(15,118,110,.08), transparent);
            animation: dc-shimmer 1.25s infinite;
          }
          @keyframes dc-spin { to { transform: rotate(360deg); } }
          @keyframes dc-shimmer { 100% { transform: translateX(100%); } }
        </style>
        </head>
        """,
    )


@st.cache_data(show_spinner=False)
def load_react_html(index_mtime: float, weather_mtime: float, geo_mtime: float, role_cache_key: str) -> str:
    del role_cache_key
    del index_mtime
    if not INDEX_HTML.exists():
        return ""
    weather_payload = build_weather_payload(weather_mtime, geo_mtime)
    return inline_vite_build(INDEX_HTML.read_text(encoding="utf-8"), weather_payload)


def main() -> None:
    if st.query_params.get("logout") == "1":
        st.session_state.clear()
        st.query_params.clear()
        st.rerun()

    if not render_login():
        return

    st.markdown(
        """
        <style>
          .stApp { background: #f6f8fb; }
          .block-container {
            max-width: none;
            padding: 0;
          }
          header[data-testid="stHeader"] {
            background: transparent;
            height: 0;
          }
          div[data-testid="stToolbar"] {
            right: 10px;
          }
          iframe {
            display: block;
            width: 100%;
            border: 0;
          }
          .fast-launch {
            margin: 16px 18px;
            padding: 14px 16px;
            border: 1px solid #dbeafe;
            border-radius: 14px;
            background: #eff6ff;
            color: #1e3a8a;
            font-size: 13px;
            font-weight: 700;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    server_status = start_react_server()
    if server_status.get("ok"):
        ensure_weather_snapshot()
        st.markdown(
            '<div class="fast-launch">로그인 확인 완료. 대시보드를 빠른 서버 모드로 연결했습니다.</div>',
            unsafe_allow_html=True,
        )
        components.iframe(react_dashboard_url(), height=980, scrolling=True)
        st.caption(
            f"연결 소스: {REACT_SERVER_URL} · 날씨 데이터: {WEATHER_SNAPSHOT_JSON} · 기존 Streamlit 앱 백업: {APP_DIR / 'app_streamlit_legacy.py'}"
        )
        return

    # Node 서버가 없는 환경(클라우드 배포 등)에서는 react_dist 빌드를 인라인해 단독 실행한다.
    if not INDEX_HTML.exists():
        st.error("React 대시보드 빌드를 찾지 못했습니다. react_dist/index.html이 필요합니다.")
        st.warning(server_status.get("error", "Unknown error"))
        return

    html = load_react_html(
        INDEX_HTML.stat().st_mtime,
        WEATHER_TIMEBLOCK_CSV.stat().st_mtime if WEATHER_TIMEBLOCK_CSV.exists() else 0.0,
        DONG_GEO_JSON.stat().st_mtime if DONG_GEO_JSON.exists() else 0.0,
        current_role(),
    )
    if not html:
        st.error("React 대시보드 빌드를 읽지 못했습니다.")
        return

    components.html(html, height=980, scrolling=True)


if __name__ == "__main__":
    main()
