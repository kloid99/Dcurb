from __future__ import annotations

import pandas as pd

from modules.load_data import first_existing, safe_float


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = low
    return max(low, min(high, value))


def build_candidates(risk: pd.Series, elastic_segments: pd.DataFrame) -> pd.DataFrame:
    dong = risk["행정동"]
    rows = []
    if not elastic_segments.empty:
        dong_col = first_existing(elastic_segments, ["행정동", "매칭_행정동"])
        if dong_col:
            segments = elastic_segments[elastic_segments[dong_col] == dong].copy()
            for _, segment in segments.iterrows():
                length = safe_float(segment.get("연장_km", 0.1), 0.1)
                rows.append(
                    {
                        "후보지명": f"{segment.get('도로명', '도로명 미상')} 탄력 하역 전환 후보",
                        "후보지유형": "기존 탄력주정차",
                        "도로명": segment.get("도로명", "-"),
                        "구간": f"{segment.get('시점', '-')} → {segment.get('종점', '-')}",
                        "기존허용시간": segment.get("허용시간대", "자료 없음"),
                        "연장_km": length,
                        "주차면수": max(4, round(length * 22)),
                        "거리_m": 120 + (len(rows) % 8) * 45,
                        "서비스반경_m": max(260, min(620, round(260 + length * 520))),
                        "source": "기존 탄력주정차",
                    }
                )

    if not rows:
        parking_spaces = int(safe_float(risk.get("탄력주정차_구간수", 0), 0) * 4 + 8)
        rows = [
            {
                "후보지명": f"{dong} 공영주차장 전환 후보",
                "후보지유형": "공영주차장",
                "도로명": "현장 검토 필요",
                "구간": "공영주차장 주변",
                "기존허용시간": "신규 지정 필요",
                "연장_km": 0,
                "주차면수": max(8, parking_spaces),
                "거리_m": 180,
                "서비스반경_m": 420,
                "source": "자동 후보",
            },
            {
                "후보지명": f"{dong} 공공시설 인근 후보",
                "후보지유형": "공공시설",
                "도로명": "현장 검토 필요",
                "구간": "행정복지센터·공공시설 주변",
                "기존허용시간": "신규 지정 필요",
                "연장_km": 0,
                "주차면수": 6,
                "거리_m": 260,
                "서비스반경_m": 360,
                "source": "자동 후보",
            },
        ]
    return pd.DataFrame(rows)


def score_candidate(candidate: pd.Series, risk: pd.Series, inputs: dict) -> float:
    distance_m = safe_float(candidate.get("거리_m", 250), 250)
    parking_spaces = safe_float(candidate.get("주차면수", 0), 0)
    distance_score = clamp(100 - distance_m / 8)
    demand_access = clamp(
        (
            safe_float(risk.get("배송수요점수_최종", 0)) * 0.55
            + safe_float(risk.get("하역부족위험", 0)) * 0.45
        )
        * (distance_score / 100)
    )
    supply = clamp(parking_spaces * 2.2 + safe_float(risk.get("탄력주정차_구간수", 0)) * 8)
    risk_access = clamp(
        safe_float(risk.get("DLFI_정규화", 50)) * 0.65
        + safe_float(risk.get("단속반복점수", 0)) * 0.35
        - distance_m / 18
    )
    traffic_safety = clamp(
        100
        - safe_float(risk.get("교통방해점수", 0)) * 0.65
        - (16 if inputs.get("start_hour", 14) < 10 or inputs.get("start_hour", 14) >= 17 else 0)
    )
    pedestrian_safety = clamp(
        100
        - safe_float(risk.get("보행충돌점수_최종", 0)) * 0.5
        - safe_float(risk.get("안전취약점수", 0)) * 0.25
    )
    operation = 90 if candidate.get("source") == "기존 탄력주정차" else 68
    confidence = 92 if str(risk.get("신뢰도등급", "")) == "높음" else 74

    total = (
        demand_access * 0.25
        + supply * 0.20
        + risk_access * 0.15
        + traffic_safety * 0.10
        + pedestrian_safety * 0.10
        + operation * 0.10
        + 82 * 0.05
        + confidence * 0.05
    )
    if inputs.get("policy_mode") == "실행 가능성 우선":
        total = total * 0.82 + operation * 0.12 + confidence * 0.06
    return round(clamp(total), 2)


def recommend_candidates(risk: pd.Series, elastic_segments: pd.DataFrame, inputs: dict) -> pd.DataFrame:
    candidates = build_candidates(risk, elastic_segments)
    candidates["적합도"] = candidates.apply(lambda row: score_candidate(row, risk, inputs), axis=1)
    return candidates.sort_values("적합도", ascending=False)
