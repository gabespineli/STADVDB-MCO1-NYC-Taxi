"""Interactive figures from approved aggregates; display controls never run SQL."""

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.analytics import (detail_rows, monthly_rows, monthly_totals,
                                 payment_composition, rush_differences, safe_heatmap)

COLORS = ["#173b63", "#d18b00", "#278178", "#96557d", "#657487", "#b85335", "#637626", "#745caa"]
BOROUGH_COLORS = dict(zip(["Manhattan", "Queens", "Brooklyn", "Bronx", "Staten Island", "EWR", "Unknown", "N/A"], COLORS))
PAYMENT_COLORS = {"Credit card": COLORS[0], "Credit Card": COLORS[0], "Cash": COLORS[1],
                  "Other": COLORS[4], "No charge": COLORS[2], "Dispute": COLORS[3],
                  "Unknown": COLORS[5], "Voided trip": COLORS[6], "Flex Fare": COLORS[7]}


def show(figure, sample, key):
    title = figure.layout.title.text or ""
    if sample:
        title += "<br><sup>SYNTHETIC SAMPLE - NOT OBSERVED</sup>"
    figure.update_layout(
        template="plotly_white", colorway=COLORS, font={"family": "Arial", "color": "#233247"},
        title={"text": title, "font": {"size": 15}, "x": 0, "xanchor": "left"},
        margin={"t": 60, "r": 24, "b": 65, "l": 20},
        legend={"title_text": "", "orientation": "h", "y": -0.18, "yanchor": "top", "x": 0},
    )
    st.plotly_chart(figure, key=key, width="stretch",
                    config={"displayModeBar": False, "displaylogo": False, "toImageButtonOptions": {"filename": key + ("_SAMPLE" if sample else "_report")}})


def heatmap(matrix, title, unit, sample, key):
    if matrix.empty:
        st.info("No groups are available for this heatmap.")
        return
    figure = px.imshow(matrix, aspect="auto", color_continuous_scale="Blues",
                        labels={"color": unit}, title=title,
                        height=max(340, min(1200, 150 + len(matrix) * 28)))
    figure.update_traces(hoverongaps=False)
    show(figure, sample, key)


def demand_charts(detail, sample, options):
    top = detail.nlargest(20, "total_filtered_pickups").sort_values("total_filtered_pickups").copy()
    top["Pickup zone"] = top.zone + " · " + top.borough
    show(px.bar(top, x="total_filtered_pickups", y="Pickup zone", color="borough", orientation="h",
                title="Top pickup zones · weekend or late-night trips", labels={"total_filtered_pickups": "Pickups", "Pickup zone": ""},
                color_discrete_map=BOROUGH_COLORS, height=max(360, min(800, len(top) * 32))), sample, "q1_demand_zones")
    if not sample and options.get("map", False):
        from dashboard.geography import render_map
        render_map(detail)
    counts = ["weekday_late_night_pickups", "weekend_late_night_pickups", "all_weekend_pickups"]
    grouped = detail.groupby("borough", as_index=False)[counts].sum(min_count=1)
    melted = grouped.melt(id_vars="borough", var_name="Measure", value_name="Pickups")
    melted["Measure"] = melted["Measure"].map(dict(zip(counts, ["Weekday late night", "Weekend late night", "All weekend"])))
    show(px.bar(melted, x="borough", y="Pickups", color="Measure", barmode="group",
                title="Borough demand · overlapping categories", color_discrete_sequence=COLORS), sample, "q1_demand_boroughs")


def hourly_charts(detail, sample, options):
    mode = options.get("mode", "Average per represented day")
    values = (["avg_weekday_hourly_pickups", "avg_weekend_hourly_pickups"]
              if mode == "Average per represented day" else ["weekday_pickups", "weekend_pickups"])
    unit = "Pickups / represented day" if mode == "Average per represented day" else "Total pickups"
    melted = detail.melt(id_vars=["borough", "hour"], value_vars=values, var_name="Day type", value_name=unit)
    melted["Day type"] = melted["Day type"].map(dict(zip(values, ["Weekday", "Weekend"])))
    rows = []
    for (borough, day), group in melted.groupby(["borough", "Day type"]):
        if group.hour.duplicated().any():
            st.warning("Multiple groups share an hour. Narrow the time-period filter before comparing.")
            return
        group = group.set_index("hour").reindex(range(24)).rename_axis("hour").reset_index()
        group["borough"], group["Day type"] = borough, day
        rows.append(group)
    melted = pd.concat(rows, ignore_index=True)
    figure = px.line(melted, x="hour", y=unit, color="Day type", facet_col="borough", facet_col_wrap=3,
                     title="Hourly demand · weekday versus weekend", labels={"hour": "Pickup hour (NYC)"},
                     color_discrete_map={"Weekday": COLORS[0], "Weekend": COLORS[1]}, height=660, markers=True)
    figure.update_xaxes(range=[0, 23], dtick=6)
    figure.update_traces(connectgaps=False)
    show(figure, sample, "q1_hourly")


def monthly_charts(detail, sample, options):
    rows = monthly_rows(detail)
    if rows.empty:
        st.info("No month-level groups are available.")
        return
    show(px.line(monthly_totals(rows), x="Month", y="late_night_pickups", markers=True,
                 title="Monthly late-night pickups · selected zones", labels={"late_night_pickups": "Pickups"},
                 color_discrete_sequence=COLORS), sample, "q1_monthly_total")
    ranking = rows.groupby("zone").late_night_pickups.sum(min_count=1).sort_values(ascending=False)
    limit = options.get("limit", 20)
    selected = ranking.index if limit == "All" else ranking.head(limit).index
    months = pd.date_range(f"{rows.Month.dt.year.min()}-01-01", f"{rows.Month.dt.year.max()}-12-01", freq="MS")
    matrix = safe_heatmap(rows[rows.zone.isin(selected)], "zone", "Month", "late_night_pickups", months).reindex(selected)
    matrix.columns = matrix.columns.strftime("%b %Y")
    heatmap(matrix, f"Late-night demand · {len(selected)} of {len(ranking)} zones", "Pickups", sample, "q1_monthly_heatmap")
    compare = options.get("compare", ranking.head(3).index.tolist())
    if compare:
        lines = rows[rows.zone.isin(compare)].set_index(["zone", "Month"])["late_night_pickups"]
        lines = lines.reindex(pd.MultiIndex.from_product([compare, months], names=["zone", "Month"])).reset_index()
        show(px.line(lines, x="Month", y="late_night_pickups", color="zone", markers=True,
                     title="Selected-zone monthly profiles", labels={"late_night_pickups": "Pickups"},
                     color_discrete_sequence=COLORS), sample, "q1_monthly_lines")


def fare_charts(detail, sample, options):
    melted = detail.melt(id_vars="fare_range", value_vars=["credit_card_trips", "cash_trips", "other_payment_trips"],
                         var_name="Payment", value_name="Trips")
    melted.Payment = melted.Payment.map({"credit_card_trips": "Credit card", "cash_trips": "Cash", "other_payment_trips": "Other"})
    melted = payment_composition(melted, ["fare_range"])
    mode = options.get("mode", "Percentage")
    axis = "Share (%)" if mode == "Percentage" else "Trips"
    figure = px.bar(melted, x="fare_range", y=axis, color="Payment", barmode="stack",
                    hover_data=["Trips", "Share (%)"], labels={"fare_range": "Fare range"},
                    title="Payment composition by fare range", color_discrete_map=PAYMENT_COLORS,
                    category_orders={"fare_range": sorted(detail.fare_range.unique())})
    if mode == "Percentage":
        figure.update_yaxes(range=[0, 100], ticksuffix="%")
    show(figure, sample, "q2_fare")


def payment_charts(detail, sample, options):
    measure = options.get("measure", "Payment share (%)")
    values = {"Payment share (%)": "Share (%)", "Trip count": "trip_count", "Mean fare ($)": "avg_fare",
              "Mean recorded tip ($)": "avg_tip", "Mean total ($)": "avg_total"}
    plotted = payment_composition(detail, ["borough", "time_period"], "trip_count")
    axis = values[measure]
    composition = measure in ("Payment share (%)", "Trip count")
    figure = px.bar(plotted, x="borough", y=axis, color="payment_method", facet_col="time_period", facet_col_wrap=2,
                    barmode="stack" if composition else "group", title=measure + " by borough and time period",
                    labels={axis: measure, "borough": "Borough", "payment_method": "Payment method"},
                    hover_data=["trip_count"], color_discrete_map=PAYMENT_COLORS, height=680)
    if measure == "Payment share (%)":
        figure.update_yaxes(range=[0, 100], ticksuffix="%")
    show(figure, sample, "q2_payment")


def rush_charts(detail, sample, options):
    mode = options.get("mode", "Extra minutes")
    if mode != "Paired duration and speed":
        plotted = rush_differences(detail)
        figure = px.bar(plotted, x="distance_bucket", y=mode, facet_col="borough", facet_col_wrap=3,
                        title="Rush hour minus off-peak · " + mode.lower(), labels={"distance_bucket": "Distance category"},
                        color_discrete_sequence=COLORS, height=670)
        figure.add_hline(y=0, line_color="#657487", line_width=1)
        show(figure, sample, "q3_comparison_difference")
        return
    for suffix, unit, title in [("duration_min", "Minutes", "Mean trip duration"), ("speed_mph", "mph", "Mean estimated speed")]:
        columns = ["rush_hour_" + suffix, "off_peak_" + suffix]
        melted = detail.melt(id_vars=["borough", "distance_bucket"], value_vars=columns, var_name="Period", value_name=unit)
        melted.Period = melted.Period.map(dict(zip(columns, ["Rush hour", "Off-peak"])))
        show(px.bar(melted, x="distance_bucket", y=unit, color="Period", facet_col="borough", facet_col_wrap=3,
                    barmode="group", title=title + " by distance category", labels={"distance_bucket": "Distance category"},
                    color_discrete_map={"Rush hour": COLORS[0], "Off-peak": COLORS[1]}, height=670), sample, "q3_comparison_" + suffix)


def location_charts(detail, sample, options):
    mode = options.get("mode", "Hourly profile")
    measure = options.get("measure", "Trip duration")
    axis = "avg_duration_minutes" if measure == "Trip duration" else "avg_speed_mph"
    unit = "Mean duration (minutes)" if measure == "Trip duration" else "Mean estimated speed (mph)"
    plotted = detail.copy()
    plotted["Pickup zone"] = plotted.borough + " · " + plotted.zone
    if mode == "Hourly profile":
        ranking = plotted.groupby("Pickup zone").trip_count.sum(min_count=1).sort_values(ascending=False)
        zone = options.get("zone", ranking.index[0])
        selected = plotted[plotted["Pickup zone"].eq(zone)]
        matrix = safe_heatmap(selected, "Pickup zone", "hour", axis, list(range(24)))
        line = matrix.T.rename_axis("Pickup hour").reset_index().rename(columns={zone: unit})
        show(px.line(line, x="Pickup hour", y=unit, markers=True, title=measure + " · " + zone,
                     color_discrete_sequence=COLORS), sample, "q3_location_hourly")
    elif mode == "Zone × hour heatmap":
        ranking = plotted.groupby("Pickup zone").trip_count.sum(min_count=1).sort_values(ascending=False)
        limit = options.get("limit", 20)
        zones = ranking.index if limit == "All" else ranking.head(limit).index
        matrix = safe_heatmap(plotted[plotted["Pickup zone"].isin(zones)], "Pickup zone", "hour", axis, list(range(24))).reindex(zones)
        heatmap(matrix, f"{measure} · {len(zones)} of {len(ranking)} zones by hour", unit, sample, "q3_location_heatmap")
    else:
        scatter = plotted[plotted.trip_count.notna() & plotted.trip_count.ge(0)]
        log_axis = options.get("log", False)
        if log_axis:
            hidden = int((scatter[axis].le(0) | scatter[axis].isna()).sum())
            scatter = scatter[scatter[axis] > 0]
            if hidden:
                st.caption(f"{hidden:,} zero/NULL groups omitted from this chart only.")
        if scatter.empty:
            st.info("No plottable values. Change the scale or filters.")
            return
        show(px.scatter(scatter, x="avg_distance_miles", y=axis, size="trip_count", color="borough", log_y=log_axis,
                        hover_name="zone", hover_data=["hour", "time_period", "trip_count"],
                        title=measure + " · weekday trips of 2–5 miles", labels={"avg_distance_miles": "Mean distance (miles)", axis: unit},
                        color_discrete_map=BOROUGH_COLORS, size_max=32, opacity=0.65, height=500), sample, "q3_location_bubbles")


RENDERERS = {"q1_demand": demand_charts, "q1_hourly": hourly_charts, "q1_monthly": monthly_charts,
             "q2_fare": fare_charts, "q2_payment": payment_charts,
             "q3_comparison": rush_charts, "q3_location": location_charts}


def render_charts(report_id, data, sample=False, options=None):
    detail = detail_rows(data)
    if detail.empty:
        st.info("No detail rows are available to chart. Complete output remains available below.")
        return
    try:
        RENDERERS[report_id](detail, sample, options or {})
    except ValueError as error:
        st.warning(str(error))
