"""Select saved aggregate groups without executing SQL or pooling averages."""

from datetime import date

import streamlit as st

from dashboard.charts import detail_rows


def filter_saved_rows(data, selections, minimum_trips=1):
    """Select existing aggregate groups; never recompute or average their rates."""
    result = detail_rows(data)
    for column, value in selections.items():
        if value is not None:
            result = result[result[column].isin(value) if isinstance(value, list) else result[column].eq(value)]
    if "trip_count" in result:
        result = result[result.trip_count >= minimum_trips]
    return result


def reset_saved_filters(prefix, report_id):
    # Assign defaults in a callback so browser widgets and data reset together.
    for column in ("borough", "zone", "time_period", "fare_range", "distance_bucket", "mo"):
        st.session_state[prefix + column] = None
    st.session_state[prefix + "minimum"] = 1
    st.session_state[prefix + "hours"] = (0, 23)
    st.session_state[report_id + "_measure"] = "Trip duration"
    st.session_state[report_id + "_log"] = False
    defaults = {
        "q1_hourly_basis": "Average per represented day", "q1_monthly_limit": 20,
        "q1_monthly_compare": [], "q2_fare_basis": "Percentage",
        "q2_payment_measure": "Payment share (%)", "q3_comparison_view": "Extra minutes",
        "q3_location_view": "Hourly profile", "q3_location_limit": 20,
        "q3_location_zone": None, "q1_demand_map": False,
    }
    for key in defaults:
        if key.startswith(report_id + "_"):
            st.session_state.pop(key, None)


def render_saved_filters(report, data, fingerprint):
    prefix = f"snapshot_{report.id}_{fingerprint[:12]}_"
    detail = detail_rows(data)
    selections = {}
    with st.container():
        st.button("Reset view", key=prefix + "reset",
                  on_click=reset_saved_filters, args=(prefix, report.id))
        candidates = [column for column in ("borough", "zone", "time_period", "fare_range", "distance_bucket", "mo") if column in detail]
        columns = st.columns(min(3, max(1, len(candidates))))
        scoped = detail
        names = {"borough": "Borough", "zone": "Taxi zone", "time_period": "Time period",
                 "fare_range": "Fare range", "distance_bucket": "Distance category", "mo": "Month"}
        for index, column in enumerate(candidates):
            options = sorted(scoped[column].dropna().unique().tolist(), key=lambda value: int(value) if column == "mo" else str(value))
            with columns[index % len(columns)]:
                value = st.selectbox(names[column], [None] + options,
                                     format_func=lambda value, column=column: "All" if value is None else date(2025, int(value), 1).strftime("%B") if column == "mo" else str(value), key=prefix + column)
            selections[column] = value
            if value is not None:
                scoped = scoped[scoped[column].eq(value)]
        minimum = 1
        if report.id == "q3_location":
            left, right = st.columns(2)
            with left:
                minimum = st.selectbox("Minimum trips per result group", [1, 10, 30, 100, 1000],
                                       key=prefix + "minimum", help="Hides small groups in this view only. The source export is unchanged.")
            with right:
                if prefix + "hours" not in st.session_state:
                    st.session_state[prefix + "hours"] = (0, 23)
                hours = st.slider("Pickup hour", 0, 23, key=prefix + "hours")
                selections["hour"] = list(range(hours[0], hours[1] + 1))
    return filter_saved_rows(data, selections, minimum), {key: value for key, value in selections.items() if value is not None}, minimum
