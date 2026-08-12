from __future__ import annotations

import pandas as pd


def event_adjusted_top(master: pd.DataFrame) -> pd.DataFrame:
    for column in ("상황반영_DLFI", "event_adjusted_dlfi", "DLFI_상황반영"):
        if column in master.columns:
            return master.sort_values(column, ascending=False)
    return master.sort_values("DLFI_최종점수", ascending=False)
