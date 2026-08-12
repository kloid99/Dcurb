from __future__ import annotations

import pandas as pd


def reliability_summary(master: pd.DataFrame) -> dict:
    if "데이터신뢰도" not in master.columns:
        return {"avg": None, "low_count": None}
    score = pd.to_numeric(master["데이터신뢰도"], errors="coerce")
    return {
        "avg": score.mean(),
        "low_count": int((score < 70).sum()),
    }
