"""Secondary chart controls, collected inside the report's Adjust view menu."""

import streamlit as st


def chart_options(report_id, data):
    options = {}
    if data.empty:
        return options
    st.divider()
    if report_id == "q1_demand":
        options["map"] = st.checkbox("Taxi-zone map", key="q1_demand_map")
    elif report_id == "q1_hourly":
        options["mode"] = st.selectbox("Hourly comparison", ["Average per represented day", "Total pickups"], key="q1_hourly_basis",
                                        help="Averages use represented dates; dates with no trips may be absent.")
    elif report_id == "q1_monthly":
        ranking = data.groupby("zone").late_night_pickups.sum(min_count=1).sort_values(ascending=False)
        options["limit"] = st.selectbox("Zones in monthly heatmap", [10, 20, 50, "All"], index=1, key="q1_monthly_limit")
        if "q1_monthly_compare" in st.session_state:
            current = st.session_state["q1_monthly_compare"]
            valid = [zone for zone in current if zone in ranking.index]
            if valid != current:
                st.session_state["q1_monthly_compare"] = valid
        options["compare"] = st.multiselect("Zones to compare over time", ranking.index.tolist(), default=ranking.head(3).index.tolist(), key="q1_monthly_compare")
    elif report_id == "q2_fare":
        options["mode"] = st.selectbox("Payment composition", ["Percentage", "Count"], key="q2_fare_basis")
    elif report_id == "q2_payment":
        options["measure"] = st.selectbox("Payment measure", ["Payment share (%)", "Trip count", "Mean fare ($)", "Mean recorded tip ($)", "Mean total ($)"], key="q2_payment_measure")
    elif report_id == "q3_comparison":
        options["mode"] = st.selectbox("Rush-hour comparison", ["Extra minutes", "Duration difference (%)", "Paired duration and speed"], key="q3_comparison_view")
    elif report_id == "q3_location":
        options["mode"] = st.selectbox("Location view", ["Hourly profile", "Zone × hour heatmap", "Bubble exploration"], key="q3_location_view")
        options["measure"] = st.selectbox("Efficiency measure", ["Trip duration", "Estimated speed"], key="q3_location_measure")
        if options["mode"] == "Hourly profile":
            labels = data.borough + " · " + data.zone
            ranking = data.assign(label=labels).groupby("label").trip_count.sum(min_count=1).sort_values(ascending=False)
            if "q3_location_zone" in st.session_state and st.session_state["q3_location_zone"] not in ranking.index:
                st.session_state["q3_location_zone"] = ranking.index[0]
            options["zone"] = st.selectbox("Zone for hourly profile", ranking.index.tolist(), key="q3_location_zone")
        elif options["mode"] == "Zone × hour heatmap":
            options["limit"] = st.selectbox("Zones in hourly heatmap", [10, 20, 50, "All"], index=1, key="q3_location_limit")
        else:
            options["log"] = st.checkbox("Logarithmic vertical scale", key="q3_location_log")
    return options
