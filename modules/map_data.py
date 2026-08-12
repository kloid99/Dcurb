from __future__ import annotations

import pandas as pd

from modules.load_data import safe_float


def build_dong_map(master: pd.DataFrame, location_master: pd.DataFrame, selected_dong: str | None = None) -> pd.DataFrame:
    if master.empty or location_master.empty:
        return pd.DataFrame()

    loc = location_master.rename(
        columns={
            "location_id": "행정동코드",
            "gu_name": "시군구",
            "location_name": "행정동",
        }
    ).copy()
    loc["행정동코드"] = loc["행정동코드"].astype(str)

    base = master.copy()
    if "행정동코드" in base.columns:
        base["행정동코드"] = base["행정동코드"].astype(str)
        merged = base.merge(loc[["행정동코드", "latitude", "longitude"]], on="행정동코드", how="left")
    else:
        merged = base.merge(loc[["행정동", "latitude", "longitude"]], on="행정동", how="left")

    merged = merged.dropna(subset=["latitude", "longitude"]).copy()
    if merged.empty:
        return merged

    score = pd.to_numeric(merged["DLFI_최종점수"], errors="coerce").fillna(0)
    lo, hi = score.min(), score.max()
    normalized = 50 if hi == lo else (score - lo) / (hi - lo) * 100
    merged["위험도_정규화"] = normalized.round(1)
    merged["map_size"] = (normalized / 100 * 750 + 120).round(0)
    merged["map_color"] = normalized.apply(color_for_score)

    if selected_dong:
        selected = merged["행정동"] == selected_dong
        merged.loc[selected, "map_size"] = merged.loc[selected, "map_size"] + 700
        merged.loc[selected, "map_color"] = "#7f1d1d"
    return merged


def build_service_radius(selected_row: pd.Series, location_master: pd.DataFrame, radius_m: int = 420) -> pd.DataFrame:
    if location_master.empty:
        return pd.DataFrame()
    dong = selected_row.get("행정동", "")
    loc = location_master[location_master["location_name"] == dong]
    if loc.empty:
        return pd.DataFrame()
    return pd.DataFrame(
        [
            {
                "행정동": dong,
                "latitude": safe_float(loc.iloc[0]["latitude"]),
                "longitude": safe_float(loc.iloc[0]["longitude"]),
                "서비스반경_m": radius_m,
                "map_size": max(300, radius_m * 2.2),
                "map_color": "#1d4ed8",
            }
        ]
    )


def build_location_marker(selected_row: pd.Series, location_master: pd.DataFrame) -> pd.DataFrame:
    if location_master.empty:
        return pd.DataFrame()
    dong = selected_row if isinstance(selected_row, str) else selected_row.get("행정동", "")
    loc = location_master[location_master["location_name"] == dong]
    if loc.empty:
        return pd.DataFrame()
    return pd.DataFrame(
        [
            {
                "행정동": dong,
                "latitude": safe_float(loc.iloc[0]["latitude"]),
                "longitude": safe_float(loc.iloc[0]["longitude"]),
                "map_size": 85,
                "map_color": "#2563eb",
            }
        ]
    )


def risk_map_deck(map_df: pd.DataFrame, selected_dong: str | None = None):
    if map_df.empty:
        return None
    try:
        import pydeck as pdk
    except ModuleNotFoundError:
        return None

    view_state = pdk.ViewState(
        latitude=safe_float(map_df["latitude"].mean(), 36.35),
        longitude=safe_float(map_df["longitude"].mean(), 127.38),
        zoom=10.25,
        pitch=0,
    )
    data = map_df.copy()
    data["radius_m"] = (pd.to_numeric(data["위험도_정규화"], errors="coerce").fillna(30) * 4 + 90).round(0)
    data["fill_color"] = data["위험도_정규화"].apply(rgba_for_score)
    data["line_color"] = data["행정동"].apply(
        lambda dong: [127, 29, 29, 255] if selected_dong and dong == selected_dong else [255, 255, 255, 190]
    )
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=data,
        get_position="[longitude, latitude]",
        get_radius="radius_m",
        get_fill_color="fill_color",
        get_line_color="line_color",
        line_width_min_pixels=1,
        stroked=True,
        filled=True,
        pickable=True,
        opacity=0.72,
    )
    text = pdk.Layer(
        "TextLayer",
        data=data[data["행정동"] == selected_dong] if selected_dong else data.head(0),
        get_position="[longitude, latitude]",
        get_text="행정동",
        get_size=16,
        get_color=[20, 35, 75, 255],
        get_angle=0,
        get_text_anchor="'middle'",
        get_alignment_baseline="'bottom'",
        pickable=False,
    )
    return pdk.Deck(
        layers=[layer, text],
        initial_view_state=view_state,
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        tooltip={
            "html": "<b>{시군구} {행정동}</b><br/>DLFI {DLFI_최종점수}<br/>위험도 {위험도_정규화}",
            "style": {"backgroundColor": "#17202a", "color": "white"},
        },
    )


def service_radius_deck(marker_df: pd.DataFrame, radius_label: str = "서비스 반경"):
    if marker_df.empty:
        return None
    try:
        import pydeck as pdk
    except ModuleNotFoundError:
        return None

    center = marker_df.iloc[0]
    view_state = pdk.ViewState(
        latitude=safe_float(center["latitude"]),
        longitude=safe_float(center["longitude"]),
        zoom=12.3,
        pitch=0,
    )
    data = marker_df.copy()
    data["radius_m"] = pd.to_numeric(data.get("서비스반경_m", data.get("map_size", 300)), errors="coerce").fillna(300)
    data["fill_color"] = [[37, 99, 235, 44] for _ in range(len(data))]
    data["point_color"] = [[37, 99, 235, 230] for _ in range(len(data))]
    radius_layer = pdk.Layer(
        "ScatterplotLayer",
        data=data,
        get_position="[longitude, latitude]",
        get_radius="radius_m",
        get_fill_color="fill_color",
        get_line_color=[37, 99, 235, 200],
        line_width_min_pixels=2,
        stroked=True,
        filled=True,
        pickable=True,
    )
    point_layer = pdk.Layer(
        "ScatterplotLayer",
        data=data,
        get_position="[longitude, latitude]",
        get_radius=55,
        get_fill_color="point_color",
        get_line_color=[255, 255, 255, 255],
        line_width_min_pixels=2,
        stroked=True,
        filled=True,
        pickable=True,
    )
    return pdk.Deck(
        layers=[radius_layer, point_layer],
        initial_view_state=view_state,
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        tooltip={
            "html": f"<b>{{행정동}}</b><br/>{radius_label}: {{서비스반경_m}}m",
            "style": {"backgroundColor": "#17202a", "color": "white"},
        },
    )


def marker_deck(marker_df: pd.DataFrame):
    if marker_df.empty:
        return None
    try:
        import pydeck as pdk
    except ModuleNotFoundError:
        return None

    center = marker_df.iloc[0]
    view_state = pdk.ViewState(
        latitude=safe_float(center["latitude"]),
        longitude=safe_float(center["longitude"]),
        zoom=13,
        pitch=0,
    )
    data = marker_df.copy()
    data["point_color"] = [[37, 99, 235, 235] for _ in range(len(data))]
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=data,
        get_position="[longitude, latitude]",
        get_radius=65,
        get_fill_color="point_color",
        get_line_color=[255, 255, 255, 255],
        line_width_min_pixels=2,
        stroked=True,
        filled=True,
        pickable=True,
    )
    return pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        tooltip={"html": "<b>{행정동}</b>", "style": {"backgroundColor": "#17202a", "color": "white"}},
    )


def color_for_score(score: float) -> str:
    score = safe_float(score)
    if score >= 75:
        return "#dc2626"
    if score >= 50:
        return "#f97316"
    if score >= 25:
        return "#facc15"
    return "#10b981"


def rgba_for_score(score: float) -> list[int]:
    score = safe_float(score)
    if score >= 75:
        return [220, 38, 38, 185]
    if score >= 50:
        return [249, 115, 22, 165]
    if score >= 25:
        return [250, 204, 21, 155]
    return [16, 185, 129, 145]
