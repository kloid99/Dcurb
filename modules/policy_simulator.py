from __future__ import annotations

import pandas as pd

from modules.candidate_sites import clamp
from modules.load_data import safe_float


def simulate_loading_zone(risk: pd.Series, score: float, inputs: dict) -> dict:
    hours = max(1, inputs["end_hour"] - inputs["start_hour"])
    hourly_capacity = inputs["bays"] * (60 / max(5, inputs["service_minutes"]))
    effective_capacity = hourly_capacity * hours * inputs["utilization"]
    estimated_demand = max(
        10,
        (
            safe_float(risk.get("배송수요점수_최종", 0)) * 0.42
            + safe_float(risk.get("하역부족위험", 0)) * 0.58
        )
        * hours
        * 0.2,
    )
    absorption = clamp(effective_capacity / estimated_demand * 100)
    quality = score / 100

    before = base_components(risk)
    after = before.copy()
    after["하역부족"] = max(0, before["하역부족"] - absorption * 0.48 * quality)
    after["단속반복"] = max(0, before["단속반복"] - absorption * 0.22 * quality)
    after["교통방해"] = max(0, before["교통방해"] - absorption * 0.16 * quality)
    after["보행충돌"] = max(0, before["보행충돌"] - absorption * 0.10 * quality)

    before_dlfi = sum(before.values())
    after_dlfi = sum(after.values())
    return {
        "effective_capacity": effective_capacity,
        "absorption": absorption,
        "before": before,
        "after": after,
        "before_dlfi": before_dlfi,
        "after_dlfi": after_dlfi,
        "delta": after_dlfi - before_dlfi,
    }


def base_components(risk: pd.Series) -> dict[str, float]:
    return {
        "배송수요": safe_float(risk.get("배송수요점수_최종", 0)),
        "교통방해": safe_float(risk.get("교통방해점수", 0)),
        "보행충돌": safe_float(risk.get("보행충돌점수_최종", 0)),
        "단속반복": safe_float(risk.get("단속반복점수", 0)),
        "안전취약": safe_float(risk.get("안전취약점수", 0)),
        "하역부족": safe_float(risk.get("하역부족위험", 100 - safe_float(risk.get("하역여유점수", 0)))),
    }


def simulate_policy(
    risk: pd.Series,
    loading_bays: int,
    delivery_dispersion_rate: int,
    weather_multiplier: float,
    tram_control: bool,
) -> dict:
    before = base_components(risk)
    after = before.copy()
    loading_effect = min(0.42, loading_bays * 0.035)
    dispersion_effect = delivery_dispersion_rate / 100

    after["하역부족"] *= 1 - loading_effect
    after["단속반복"] *= 1 - loading_effect * 0.55
    after["배송수요"] *= 1 - dispersion_effect * 0.35
    after["교통방해"] *= 1 - dispersion_effect * 0.25

    if weather_multiplier > 1:
        after["교통방해"] *= weather_multiplier
        after["보행충돌"] *= min(1.25, weather_multiplier)
    if tram_control:
        after["교통방해"] *= 1.12
        after["단속반복"] *= 1.06

    before_score = sum(before.values())
    after_score = sum(after.values())
    return {
        "before": before,
        "after": after,
        "before_score": before_score,
        "after_score": after_score,
        "delta": after_score - before_score,
    }
