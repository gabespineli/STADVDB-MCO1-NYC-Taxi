"""Plotly figures from aggregated results; never pool subgroup averages."""

import pandas as pd
import plotly.express as px
import streamlit as st

COLORS = ["#173b63", "#d18b00", "#278178", "#96557d", "#657487"]
ROLLUP_LABELS = {
    "borough": {"ALL BOROUGHS"}, "zone": {"Borough Subtotal", "ALL ZONES"},
    "time_period": {"All Time Periods"}, "payment_method": {"All Payment Methods"},
    "fare_range": {"ALL FARE TIERS"}, "distance_bucket": {"All Distance Tiers"},
}


def detail_rows(data):
    result = data.copy()
    for column, labels in ROLLUP_LABELS.items():
        if column in result:
            result = result[result[column].notna() & ~result[column].isin(labels)]
    for column in ("yr", "qtr", "mo"):
        if column in result:
            result = result[pd.to_numeric(result[column], errors="coerce").notna()]
    return result


def show(figure, sample, key):
    title = figure.layout.title.text or ""
    if sample:
        title += "<br><sup>SYNTHETIC SAMPLE — NOT OBSERVED</sup>"
    figure.update_layout(
        template="plotly_white", colorway=COLORS, font={"family": "Arial", "color": "#233247"},
        title={"text": title, "font": {"size": 14}, "x": 0, "xanchor": "left"},
        margin={"t": 75, "r": 20, "b": 110, "l": 20},
        legend={"title_text": "", "orientation": "h", "y": -0.25, "yanchor": "top", "x": 0},
    )
    st.plotly_chart(figure, key=key,
                    config={"displaylogo": False, "toImageButtonOptions": {"filename": key + ("_SAMPLE" if sample else "_warehouse")}})


def render_charts(report_id, data, sample):
    detail = detail_rows(data)
    if detail.empty:
        st.info("No detail rows are available to chart. The returned result, including rollups, is shown below.")
        return
    if report_id == "q1_demand":
        top = detail.nlargest(20, "total_filtered_pickups").sort_values("total_filtered_pickups")
        show(px.bar(top, x="total_filtered_pickups", y="zone", color="borough", orientation="h",
                    title="Top 20 zones · weekend or late-night pickups", labels={"total_filtered_pickups": "Pickups", "zone": ""},
                    color_discrete_sequence=COLORS, height=max(360, min(760, len(top) * 30))), sample, report_id + "_zones")
        st.caption("The zone chart shows up to 20 groups by pickup count. All filtered detail groups contribute to the borough comparison and result table.")
        counts = ["weekday_late_night_pickups", "weekend_late_night_pickups", "all_weekend_pickups"]
        grouped = detail.groupby("borough", as_index=False)[counts].sum(min_count=1)
        melted = grouped.melt(id_vars="borough", var_name="Measure", value_name="Pickups")
        melted["Measure"] = melted["Measure"].map(dict(zip(counts, ["Weekday late night", "Weekend late night", "All weekend"])))
        show(px.bar(melted,
                    x="borough", y="Pickups", color="Measure", barmode="group", title="Borough demand comparisons",
                    color_discrete_sequence=COLORS), sample, report_id + "_boroughs")
    elif report_id == "q1_hourly":
        melted = detail.melt(id_vars=["borough", "hour"], value_vars=["weekday_pickups", "weekend_pickups"],
                             var_name="Day type", value_name="Pickups")
        melted["Day type"] = melted["Day type"].map({"weekday_pickups": "Weekday", "weekend_pickups": "Weekend"})
        show(px.line(melted.sort_values("hour"), x="hour", y="Pickups", color="Day type",
                     facet_col="borough", facet_col_wrap=3, title="Hourly pickups · weekday and weekend",
                     color_discrete_sequence=COLORS, height=570, markers=True), sample, report_id)
    elif report_id == "q1_monthly":
        detail = detail.copy()
        detail["year"] = pd.to_numeric(detail["yr"], errors="coerce")
        detail["month"] = pd.to_numeric(detail["mo"], errors="coerce")
        detail = detail[detail["year"].notna() & detail["month"].between(1, 12)]
        if detail.empty:
            st.info("No month-level detail rows are available. Date subtotal rows are not charted.")
            return
        grouped = detail.groupby(["year", "month"], as_index=False)["late_night_pickups"].sum(min_count=1)
        grouped["Month"] = pd.to_datetime(dict(year=grouped["year"].astype(int), month=grouped["month"].astype(int), day=1))
        show(px.line(grouped.sort_values("Month"), x="Month", y="late_night_pickups", markers=True,
                     labels={"late_night_pickups": "Late-night pickups"}, title="Monthly late-night demand",
                     color_discrete_sequence=COLORS), sample, report_id)
    elif report_id == "q2_fare":
        melted = detail.melt(id_vars="fare_range", value_vars=["credit_card_trips", "cash_trips", "other_payment_trips"],
                             var_name="Payment", value_name="Trips")
        melted["Payment"] = melted["Payment"].map({"credit_card_trips": "Credit card", "cash_trips": "Cash", "other_payment_trips": "Other"})
        show(px.bar(melted, x="fare_range", y="Trips", color="Payment", barmode="stack",
                    labels={"fare_range": "Fare range"}, title="Payment composition by fare range",
                    color_discrete_sequence=COLORS), sample, report_id)
    elif report_id == "q2_payment":
        show(px.bar(detail, x="borough", y="trip_count", color="payment_method", facet_col="time_period",
                    facet_col_wrap=2, barmode="stack", title="Payment distribution by borough and time period",
                    labels={"trip_count": "Trips", "payment_method": "Payment method", "borough": "Borough"},
                    color_discrete_sequence=COLORS, height=540), sample, report_id)
    elif report_id == "q3_comparison":
        for suffix, unit, title in [("duration_min", "Minutes", "Mean trip duration"), ("speed_mph", "mph", "Mean estimated speed")]:
            columns = ["rush_hour_" + suffix, "off_peak_" + suffix]
            melted = detail.melt(id_vars=["borough", "distance_bucket"], value_vars=columns,
                                 var_name="Period", value_name=unit)
            melted["Period"] = melted["Period"].map({columns[0]: "Rush hour", columns[1]: "Off-peak"})
            show(px.bar(melted, x="distance_bucket", y=unit, color="Period", facet_col="borough",
                        facet_col_wrap=3, barmode="group", title=title + " by distance category",
                        labels={"distance_bucket": "Distance category"}, color_discrete_sequence=COLORS,
                        height=620), sample, report_id + suffix)
    elif report_id == "q3_location":
        scatter = detail[detail["trip_count"].notna() & (detail["trip_count"] >= 0)]
        if scatter.empty:
            st.info("No valid trip-count values are available for the location chart.")
            return
        measure = st.radio("Efficiency measure", ["Trip duration", "Estimated speed"], horizontal=True, key=report_id + "_measure")
        axis = "avg_duration_minutes" if measure == "Trip duration" else "avg_speed_mph"
        log_axis = st.checkbox("Logarithmic vertical scale", key=report_id + "_log", help="Useful for viewing a wide range. Only positive values can be drawn on a logarithmic axis.")
        if log_axis:
            hidden = int((scatter[axis].le(0) | scatter[axis].isna()).sum())
            scatter = scatter[scatter[axis] > 0]
            if hidden:
                st.caption(f"{hidden:,} groups with zero or missing values cannot appear on the logarithmic chart; they remain in the result table.")
        if scatter.empty:
            st.info("No plottable values for this scale. Switch off the logarithmic scale or change the filters.")
            return
        show(px.scatter(scatter, x="avg_distance_miles", y=axis, size="trip_count", color="borough", log_y=log_axis,
                        hover_name="zone", hover_data=["hour", "time_period", "avg_speed_mph", "trip_count"],
                        title=measure + " by pickup location · weekday trips of 2–5 miles",
                        labels={"avg_distance_miles": "Mean distance (miles)", "avg_duration_minutes": "Mean duration (minutes)",
                                "avg_speed_mph": "Mean estimated speed (mph)"}, color_discrete_sequence=COLORS,
                        size_max=32, opacity=0.65, height=500), sample, report_id)
        st.caption("Each point is an existing zone × pickup hour × time-period group. Bubble size represents trips. Hover to inspect a group; use the legend to focus on a borough.")
