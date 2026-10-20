"""Official taxi-zone polygons and conservative joins to aggregate report groups."""

import gzip
import json
import math
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
BOUNDARIES = ROOT / "reference_data" / "taxi_zones.geojson.gz"
LOOKUP = ROOT / "reference_data" / "taxi_zone_lookup.csv"


def validate_boundaries(data, lookup):
    if not isinstance(data, dict) or data.get("type") != "FeatureCollection" or not data.get("features"):
        raise ValueError("Taxi-zone boundaries must be a nonempty GeoJSON FeatureCollection.")
    known = set(lookup.LocationID.astype(str))
    features, identities = {}, {}
    for feature in data["features"]:
        properties = {key.lower(): value for key, value in feature.get("properties", {}).items()}
        zone_id = str(properties.get("locationid", properties.get("location_id", "")))
        if zone_id not in known:
            raise ValueError("Taxi-zone boundary IDs must be present in the official lookup.")
        identity = (properties.get("borough"), properties.get("zone"))
        if zone_id in identities and identities[zone_id] != identity:
            raise ValueError("Repeated boundary IDs must describe the same taxi zone.")
        geometry = feature.get("geometry") or {}
        if geometry.get("type") not in ("Polygon", "MultiPolygon"):
            raise ValueError("Taxi-zone boundaries must contain polygon geometry.")
        polygons = [geometry.get("coordinates")] if geometry["type"] == "Polygon" else geometry.get("coordinates")
        if not polygons:
            raise ValueError("A taxi-zone polygon is empty.")
        for polygon in polygons:
            if not polygon:
                raise ValueError("A taxi-zone polygon is empty.")
            for ring in polygon:
                if len(ring) < 4 or ring[0] != ring[-1]:
                    raise ValueError("Taxi-zone polygon rings must be closed.")
                for point in ring:
                    if (len(point) < 2 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in point[:2])
                            or not -75 < point[0] < -72 or not 39 < point[1] < 42):
                        raise ValueError("Taxi-zone coordinates must use NYC-area longitude and latitude.")
        # The official export has split features for IDs 56 and 103. Combine
        # their polygon parts, retaining one feature per ID so counts cannot fan out.
        if zone_id not in features:
            features[zone_id] = {"type": "Feature", "id": zone_id, "properties": {"location_id": zone_id},
                                 "geometry": {"type": "MultiPolygon", "coordinates": []}}
        features[zone_id]["geometry"]["coordinates"].extend(polygons)
        identities[zone_id] = identity
    return {"type": "FeatureCollection", "features": list(features.values())}


@st.cache_data(show_spinner=False)
def load_geography():
    try:
        lookup = pd.read_csv(LOOKUP, dtype=str, keep_default_na=False)
        with gzip.open(BOUNDARIES, "rt", encoding="utf-8") as handle:
            data = json.load(handle)
        return validate_boundaries(data, lookup), lookup
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError("Taxi-zone map boundaries are unavailable or invalid. Rankings and downloads remain available.") from None


def match_groups(data, lookup, geojson):
    """A borough/zone label must identify exactly one official ID; never fan out counts."""
    mapping = lookup.rename(columns={"Borough": "borough", "Zone": "zone", "LocationID": "location_id"})
    mapping = mapping[["borough", "zone", "location_id"]].drop_duplicates()
    ambiguous = mapping.duplicated(["borough", "zone"], keep=False)
    unique = mapping[~ambiguous]
    result = data.merge(unique, on=["borough", "zone"], how="left", validate="many_to_one")
    ambiguous_keys = set(map(tuple, mapping.loc[ambiguous, ["borough", "zone"]].values))
    ids = {feature["id"] for feature in geojson["features"]}
    result["Map status"] = [
        "Ambiguous taxi-zone label" if (row.borough, row.zone) in ambiguous_keys else
        "No lookup match" if pd.isna(row.location_id) else
        "No polygon for this ID" if row.location_id not in ids else "Mapped"
        for row in result.itertuples()
    ]
    return result


def render_map(data):
    from dashboard.charts import show
    try:
        geojson, lookup = load_geography()
        joined = match_groups(data, lookup, geojson)
    except ValueError as error:
        st.info(str(error))
        return
    mapped = joined[joined["Map status"].eq("Mapped")]
    unmatched = joined[~joined["Map status"].eq("Mapped")]
    if not mapped.empty:
        figure = px.choropleth_map(mapped, geojson=geojson, featureidkey="id", locations="location_id",
                                   color="total_filtered_pickups", hover_name="zone", hover_data=["borough"],
                                   color_continuous_scale="Blues", map_style="white-bg",
                                   center={"lat": 40.72, "lon": -73.94}, zoom=9,
                                   title="Weekend / late-night pickups by taxi zone",
                                   labels={"total_filtered_pickups": "Pickups"}, height=550)
        show(figure, False, "q1_demand_map_figure")
    else:
        st.info("No selected groups have an unambiguous boundary match.")
    st.caption(f"{len(mapped):,} of {len(joined):,} groups mapped · pickups per taxi zone")
    if not unmatched.empty:
        with st.expander("Groups outside the map"):
            st.dataframe(unmatched[["borough", "zone", "total_filtered_pickups", "Map status"]], hide_index=True, width="stretch")
