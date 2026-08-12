from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from modules.load_data import DATA_DIR


WEATHER_SCENARIOS = {
    "맑음": 1.00,
    "비": 1.10,
    "폭우": 1.22,
    "강풍": 1.15,
    "폭염": 1.08,
}


def load_weather_snapshot() -> dict:
    path = DATA_DIR / "weather_risk_snapshot.json"
    if not path.exists():
        return {"status": "fallback", "message": "실시간 스냅샷 없음", "risk": "보통"}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "error", "message": "스냅샷 JSON 오류", "risk": "확인 필요"}


def weather_for_dong(weather_time: pd.DataFrame, dong: str) -> pd.DataFrame:
    if weather_time.empty or "location_name" not in weather_time.columns:
        return pd.DataFrame()
    return weather_time[weather_time["location_name"] == dong].copy()
