"""Scopes, definitions, and summaries shared by saved, sample, and live reports."""

import pandas as pd
import streamlit as st

from dashboard.analytics import detail_rows, rush_differences, monthly_totals

SCOPES = {
    "q1_demand": "2025 · Pickups on weekends OR during Late Night · Pickup borough × zone",
    "q1_hourly": "2025 · Pickups by borough, hour, and day type · NYC local clock time",
    "q1_monthly": "2025 · Late-night pickups · Taxi zone × month",
    "q2_fare": "2025 · Trips with positive fares · Fare tier × recorded payment counts",
    "q2_payment": "2025 · Trips with positive fares · Pickup borough × time period × payment method",
    "q3_comparison": "2025 · Weekdays, positive distance and duration · Pickup borough × distance category",
    "q3_location": "2025 · Weekday trips of 2–5 miles, positive duration · Pickup zone × hour × period",
}
CAUTIONS = {
    "q1_demand": "Weekend late-night pickups are already included in all-weekend pickups. These comparison series overlap and must not be added.",
    "q1_hourly": "Daily averages use dates represented in each borough/hour group; zero-trip dates may be absent. Total pickups reflect different numbers of weekday and weekend dates.",
    "q1_monthly": "Counts describe volume, not trips per day. Month lengths differ; a missing month is unknown, not zero.",
    "q2_fare": "Only credit-card tips are recorded by TLC; cash tips are not captured. Mean recorded tips across all payment types are not a card-only tipping measure.",
    "q2_payment": "Cash tips are not captured. Fare, recorded tip, and total are separate returned group means; they are not averaged across groups.",
    "q3_comparison": "Differences compare reported group means: rush hour minus off-peak. They are descriptive, not evidence that rush hour caused the difference. No subgroup means are pooled.",
    "q3_location": "Speed is the mean of individual trip speeds. Missing hourly groups remain gaps. Small groups and flagged extremes remain in the data and downloads.",
}


def format_number(value, decimals=0):
    return "Unavailable" if pd.isna(value) else f"{value:,.{decimals}f}"


def metrics(report_id, data):
    """Return label/value pairs computed only at each report's valid grain."""
    data = detail_rows(data)
    if data.empty:
        return []
    if report_id == "q1_demand":
        total = data.total_filtered_pickups.sum(min_count=1)
        valid = data.dropna(subset=["total_filtered_pickups"])
        peak = valid.loc[valid.total_filtered_pickups.idxmax()] if not valid.empty else None
        leader = f"{peak.zone} ({peak.borough})" if peak is not None else "Unavailable"
        return [("Weekend / late-night pickups", format_number(total)), ("Busiest selected zone", leader)]
    if report_id == "q1_hourly":
        valid = data.dropna(subset=["avg_weekday_hourly_pickups"])
        peak = valid.loc[valid.avg_weekday_hourly_pickups.idxmax()] if not valid.empty else None
        label = f"{peak.borough} · {int(peak.hour):02}:00" if peak is not None else "Unavailable"
        value = format_number(peak.avg_weekday_hourly_pickups, 1) if peak is not None else "Unavailable"
        return [("Pickups in selected groups", format_number(data[["weekday_pickups", "weekend_pickups"]].sum(min_count=1).sum(min_count=1))),
                ("Peak weekday group", label), ("Pickups / represented weekday at peak", value)]
    if report_id == "q1_monthly":
        return [("Selected late-night pickups", format_number(data.late_night_pickups.sum(min_count=1))),
                ("Selected taxi zones", str(data.zone.nunique()))]
    if report_id == "q2_fare":
        total = data.total_trips.sum(min_count=1)
        share = 100 * data.credit_card_trips.sum(min_count=1) / total if pd.notna(total) and total > 0 else float("nan")
        return [("Selected positive-fare trips", format_number(total)),
                ("Credit-card share", format_number(share, 1) + ("%" if pd.notna(share) else ""))]
    if report_id == "q2_payment":
        return [("Selected positive-fare trips", format_number(data.trip_count.sum(min_count=1))),
                ("Payment methods shown", str(data.payment_method.nunique()))]
    if report_id == "q3_comparison":
        valid = rush_differences(data).dropna(subset=["Extra minutes"])
        peak = valid.loc[valid["Extra minutes"].idxmax()] if not valid.empty else None
        return [("Largest selected duration difference", (f"{peak['Extra minutes']:+.1f} min" if peak is not None else "Unavailable")),
                ("Comparison group", f"{peak.borough} · {peak.distance_bucket}" if peak is not None else "Unavailable")]
    return [("Trips in selected location groups", format_number(data.trip_count.sum(min_count=1))),
            ("Pickup zones shown", str(len(data[["borough", "zone"]].drop_duplicates())))]


def render_context(report, data, selections=None, minimum=1):
    active = []
    for name, value in (selections or {}).items():
        if name == "hour":
            if value and value != list(range(24)):
                active.append(f"hours: {min(value):02}:00–{max(value):02}:59")
        else:
            active.append(f"{name.replace('_', ' ')}: {value}")
    if minimum > 1:
        active.append(f"at least {minimum:,} trips per group")
    if active:
        st.caption(" · ".join(active))
    pairs = metrics(report.id, data)
    if report.id in ("q1_demand", "q3_comparison"):
        pairs = pairs[:1]
    elif report.id == "q1_hourly":
        pairs = [pairs[0], pairs[2]] if len(pairs) == 3 else pairs
    for column, (label, value) in zip(st.columns(max(1, len(pairs))), pairs):
        column.metric(label, value)


SHORT_NOTES = {
    "q1_demand": "Weekend categories overlap.",
    "q1_hourly": "Averages use represented dates; missing hours are gaps.",
    "q1_monthly": "Blank months are missing, not zero.",
    "q2_fare": "Cash tips are not recorded.",
    "q2_payment": "Cash tips are not recorded; dollar values are group means.",
    "q3_comparison": "Observed difference, not a causal estimate.",
    "q3_location": "Blank hours are missing; values are group means.",
}


def insight(report_id, data):
    """One complementary finding, calculated from the selected detail groups."""
    data = detail_rows(data)
    if data.empty:
        return ""
    if report_id == "q1_demand":
        valid = data.dropna(subset=["total_filtered_pickups"])
        total = data.total_filtered_pickups.sum(min_count=1)
        if not valid.empty and total > 0:
            peak = valid.loc[valid.total_filtered_pickups.idxmax()]
            return f"{peak.zone} accounts for {100 * peak.total_filtered_pickups / total:.1f}% of selected pickups."
    elif report_id == "q1_hourly":
        valid = data.dropna(subset=["avg_weekday_hourly_pickups", "hour"])
        if not valid.empty:
            peak = valid.loc[valid.avg_weekday_hourly_pickups.idxmax()]
            return f"The busiest weekday group is {peak.borough} at {int(peak.hour):02}:00."
    elif report_id == "q1_monthly":
        valid = monthly_totals(data).dropna(subset=["late_night_pickups"])
        if not valid.empty:
            peak = valid.loc[valid.late_night_pickups.idxmax()]
            return f"Selected late-night demand peaks in {peak.Month.strftime('%B')} at {peak.late_night_pickups:,.0f} pickups."
    elif report_id in ("q2_fare", "q2_payment"):
        if report_id == "q2_fare":
            valid = data[data.total_trips > 0].copy()
            valid["share"] = 100 * valid.credit_card_trips / valid.total_trips
            valid = valid.dropna(subset=["share"])
            if not valid.empty:
                peak = valid.loc[valid.share.idxmax()]
                return f"Card share is highest in {peak.fare_range.split('. ', 1)[-1]} fares: {peak.share:.1f}%."
        else:
            counts = data.groupby("payment_method").trip_count.sum(min_count=1).dropna()
            total = counts.sum(min_count=1)
            if not counts.empty and total > 0:
                return f"{counts.idxmax()} represents {100 * counts.max() / total:.1f}% of selected trips."
    elif report_id == "q3_comparison":
        pairs = metrics(report_id, data)
        return f"Largest duration gap: {pairs[1][1]}."
    return ""
