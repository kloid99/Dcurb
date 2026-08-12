from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st


APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR / "data"


def read_header(path: Path) -> list[str]:
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            with path.open("r", encoding=encoding, newline="") as file:
                return next(csv.reader(file))
        except UnicodeDecodeError:
            continue
        except StopIteration:
            return []
    return []


def find_file(*patterns: str) -> Path | None:
    for pattern in patterns:
        matches = sorted(DATA_DIR.rglob(pattern))
        if matches:
            return matches[0]
    return None


def find_csv_with_columns(required: Iterable[str]) -> Path | None:
    required = set(required)
    for path in sorted(DATA_DIR.rglob("*.csv")):
        if required.issubset(set(read_header(path))):
            return path
    return None


@st.cache_data(show_spinner=False)
def read_csv_auto(path: str | Path | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame()
    path = Path(path)
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, encoding="utf-8", encoding_errors="replace")


@st.cache_data(show_spinner=False)
def load_data() -> dict[str, pd.DataFrame]:
    paths = {
        "model": find_file("final_modelling.csv"),
        "elastic_dashboard": find_csv_with_columns(["행정동", "탄력주정차_구간수", "총연장_km"]),
        "elastic_segments": find_csv_with_columns(["도로명", "시점", "종점", "허용시간대"]),
        "logistics_time": find_file("logistics_view_timeband_v3.csv"),
        "driver_time": find_file("driver_view_timeband_v3.csv", "driver_view_timeband_v2.csv"),
        "policy_text": find_file("driver_facing_policy_text.csv"),
        "risk_type": find_file("risk_type_master.csv"),
        "reliability": find_file("reliability_score.csv", "reliability_master.csv", "RELIAB~1.CSV"),
        "tram": find_file("tram/tram_segment_dong_final.csv", "tram_segment_dong_final.csv"),
        "tram_event": find_file("tram/tram_event_risk_dong.csv", "tram_event_risk_dong.csv"),
        "event_adjusted": find_file(
            "event_adjusted_dlfi.csv",
            "tram/DLFI_MASTER_v5_with_tram_event_risk.csv",
            "DLFI_MASTER_v5_with_tram_event_risk.csv",
        ),
        "feedback": find_file("driver_feedback_sample.csv"),
        "weather_time": find_file("weather/dlfi_weather_timeblock_input_latest.csv"),
        "weather_nextday": find_file("weather/dlfi_weather_nextday_input_ready.csv"),
        "weather_location": find_file("weather/daejeon_weather_location_master.csv"),
        "openmeteo_hourly": find_file("7 days weather/daejeon_openmeteo_hourly_7days.csv"),
        "openmeteo_timeblock": find_file("7 days weather/daejeon_openmeteo_timeblock_7days.csv"),
        "openmeteo_gu_summary": find_file("7 days weather/daejeon_openmeteo_gu_summary_7days.csv"),
        "openmeteo_dong_daily": find_file("7 days weather/daejeon_openmeteo_dong_daily_7days.csv"),
        "openmeteo_top10": find_file("7 days weather/daejeon_openmeteo_weather_top10_7days.csv"),
        "openmeteo_quality": find_file("7 days weather/daejeon_openmeteo_7days_quality_report.csv"),
    }
    return {name: read_csv_auto(path) for name, path in paths.items()}


def to_num(series: pd.Series, default: float = 0) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(default)


def safe_float(value, default: float = 0.0) -> float:
    value = pd.to_numeric(value, errors="coerce")
    if pd.isna(value):
        return default
    return float(value)


def first_existing(df: pd.DataFrame, columns: Iterable[str]) -> str | None:
    return next((column for column in columns if column in df.columns), None)


def prepare_master(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    model = data["model"].copy()
    if model.empty:
        return model

    model["DLFI_최종점수"] = to_num(model["DLFI_최종점수"])
    lo, hi = model["DLFI_최종점수"].min(), model["DLFI_최종점수"].max()
    model["DLFI_정규화"] = 50 if hi == lo else (model["DLFI_최종점수"] - lo) / (hi - lo) * 100

    for key in ("elastic_dashboard", "risk_type", "reliability", "event_adjusted", "tram_event"):
        df = data.get(key, pd.DataFrame())
        if not df.empty and "행정동" in df.columns:
            add_cols = [column for column in df.columns if column not in model.columns or column == "행정동"]
            model = model.merge(df[add_cols], on="행정동", how="left", suffixes=("", f"_{key}"))
    return model
