from __future__ import annotations

import pandas as pd


def tram_for_dong(tram_df: pd.DataFrame, dong: str) -> pd.DataFrame:
    if tram_df.empty:
        return pd.DataFrame()
    for column in ("행정동", "동명", "location_name"):
        if column in tram_df.columns:
            return tram_df[tram_df[column] == dong].copy()
    return pd.DataFrame()


def has_tram_control(tram_df: pd.DataFrame, dong: str) -> bool:
    return not tram_for_dong(tram_df, dong).empty
