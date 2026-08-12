from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from modules.load_data import DATA_DIR


FEEDBACK_PATH = DATA_DIR / "driver_feedback_sample.csv"


def save_feedback(dong: str, feedback_type: str, memo: str) -> None:
    row = pd.DataFrame(
        [
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "행정동": dong,
                "피드백유형": feedback_type,
                "메모": memo,
            }
        ]
    )
    if FEEDBACK_PATH.exists():
        existing = pd.read_csv(FEEDBACK_PATH, encoding="utf-8-sig")
        row = pd.concat([existing, row], ignore_index=True)
    row.to_csv(FEEDBACK_PATH, index=False, encoding="utf-8-sig")
