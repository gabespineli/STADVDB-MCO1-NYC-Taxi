"""Only expose working filters when their SQL bindings are explicitly approved."""

from datetime import date

import streamlit as st

from dashboard.sample_data import DISTANCES


def render_filters(report, config, readiness, enabled):
    bindings = config.get("filters", {}) if enabled else {}
    locations = readiness.get("locations", [])
    boroughs = sorted({row["borough"] for row in locations if row["borough"]})
    zones = sorted({row["zone"] for row in locations if row["zone"]})
    values = {}
    with st.expander("Report filters", expanded=bool(bindings)):
        if not bindings:
            st.caption("Filters are waiting for validated SQL parameters. The controls below do not change the preview.")
        else:
            st.caption("Filters apply to this report when you select Load warehouse report.")
        with st.form(f"filters_{report.id}"):
            left, middle, right = st.columns(3)
            with left:
                borough = st.selectbox("Borough", ["All boroughs"] + boroughs,
                                       disabled="borough" not in bindings)
                values["borough"] = None if borough == "All boroughs" else borough
                zone = st.selectbox("Taxi zone", ["All zones"] + zones, disabled="zone" not in bindings)
                values["zone"] = None if zone == "All zones" else zone
                month = st.selectbox("Month", ["All months"] + list(range(1, 13)),
                                     format_func=lambda value: value if isinstance(value, str) else date(2025, value, 1).strftime("%B"),
                                     disabled="month" not in bindings)
                values["month"] = None if month == "All months" else month
            with middle:
                dates = st.date_input("Pickup date range", value=(date(2025, 1, 1), date(2025, 12, 31)),
                                      min_value=date(2025, 1, 1), max_value=date(2025, 12, 31),
                                      disabled="start_date" not in bindings)
                period = st.selectbox("Time period", ["All periods"] + sorted(value for value in readiness.get("time_periods", []) if value),
                                      disabled="time_period" not in bindings)
                values["time_period"] = None if period == "All periods" else period
                distance = st.selectbox("Distance category", ["All distances"] + DISTANCES,
                                        disabled="distance_category" not in bindings)
                values["distance_category"] = None if distance == "All distances" else distance
            with right:
                limit_fares = st.checkbox("Limit fare range", disabled="fare_min" not in bindings)
                fare_min = st.number_input("Minimum fare ($)", value=0.0, min_value=0.0,
                                           disabled="fare_min" not in bindings)
                fare_max = st.number_input("Maximum fare ($)", value=100.0, min_value=0.0,
                                           disabled="fare_max" not in bindings)
                st.caption("Fare bounds apply only when Limit fare range is checked.")
                values["fare_min"] = fare_min if limit_fares else None
                values["fare_max"] = fare_max if limit_fares else None
                aggregation = st.selectbox("Aggregation level", ["Zone", "Borough"],
                                           disabled="aggregation" not in bindings)
                values["aggregation"] = aggregation
            submitted = st.form_submit_button("Load warehouse report", disabled=not enabled, type="primary")
    error = None
    if "start_date" in bindings:
        if len(dates) != 2:
            error = "Select both the start and end of the date range."
        else:
            values["start_date"], values["end_date"] = dates
    if limit_fares and fare_min > fare_max:
        error = "Minimum fare must not exceed maximum fare."
    if submitted and error:
        st.error(error)
    parameters = {parameter: values[control] for control, parameter in bindings.items() if control in values}
    return submitted and not error, parameters
