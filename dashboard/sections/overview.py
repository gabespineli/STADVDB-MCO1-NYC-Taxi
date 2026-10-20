"""An overview of completed saved exports, with concise data-derived findings."""

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.analytics import detail_rows, monthly_totals, rush_differences
from dashboard.charts import COLORS, PAYMENT_COLORS, show
from dashboard.presentation import CAUTIONS, SCOPES, insight, metrics
from dashboard.reports import REPORTS
from dashboard.snapshots import load_export


def collect_results(exports):
    results, sources = {}, []
    for report in REPORTS:
        source, status = "Unavailable", "Awaiting export"
        try:
            if exports[report.id]:
                result = load_export(report, exports[report.id][0])
                if not detail_rows(result["data"]).empty:
                    results[report.id] = result["data"]
                    source, status = result["filename"], result["exported_at"]
                else:
                    status = "No detail groups"
        except ValueError as error:
            status = str(error)
        sources.append({"Report": report.title, "Updated": status, "File": source})
    return results, pd.DataFrame(sources)


def render(exports):
    data, sources = collect_results(exports)
    if not data:
        st.info("Awaiting completed exports.")
    distance = None
    adjust, source, _ = st.columns([1.5, 1, 7.5])
    with adjust:
        with st.popover("Adjust view", icon=":material/tune:", width="stretch"):
            if "q3_comparison" in data:
                compared = detail_rows(data["q3_comparison"])
                distance = st.selectbox("Rush-hour distance", sorted(compared.distance_bucket.unique()), key="overview_distance",
                                        help="Applies to the duration-gap chart; overview metrics use each complete report.")
            else:
                st.caption("All available results are shown.")
    with source:
        with st.popover("Data", icon=":material/table_view:", width="stretch"):
            st.dataframe(sources, hide_index=True, width="stretch")
            st.caption("Full report populations. Trip counts across reports overlap and must not be added.")
            if data:
                report_id = st.selectbox("Export report", list(data), format_func=lambda key: next(r.title for r in REPORTS if r.id == key), key="overview_export")
                st.caption(SCOPES[report_id])
                st.caption(CAUTIONS[report_id])
                st.download_button("Download CSV", data[report_id].to_csv(index=False, na_rep="\\N").encode("utf-8-sig"),
                                   file_name=report_id + "_complete.csv", mime="text/csv")
    for column, report_id, index, label in zip(st.columns(3),
            ["q1_demand", "q2_fare", "q3_comparison"], [0, 1, 0],
            ["Weekend / late-night pickups", "Card share · positive fares", "Largest rush-hour gap"]):
        pairs = metrics(report_id, data[report_id]) if report_id in data else []
        column.metric(label, pairs[index][1] if pairs else "Unavailable")
    if "q1_monthly" in data:
        show(px.line(monthly_totals(data["q1_monthly"]), x="Month", y="late_night_pickups", markers=True,
                     title="Late-night demand", labels={"late_night_pickups": "Pickups"}, color_discrete_sequence=COLORS), False, "overview_monthly")
        st.caption(insight("q1_monthly", data["q1_monthly"]))
    if "q2_fare" in data:
        fare = detail_rows(data["q2_fare"])
        counts = fare[["credit_card_trips", "cash_trips", "other_payment_trips"]].sum(min_count=1)
        counts.index = ["Credit card", "Cash", "Other"]
        total = counts.sum(min_count=1)
        composition = counts.rename_axis("Payment").reset_index(name="Trips")
        composition["Share (%)"] = 100 * composition.Trips / total if pd.notna(total) and total > 0 else float("nan")
        show(px.bar(composition, x="Share (%)", y="Payment", color="Payment", orientation="h",
                    hover_data=["Trips"], title="Payment mix · positive-fare trips",
                    color_discrete_map=PAYMENT_COLORS, range_x=[0, 100]), False, "overview_payments")
        st.caption(insight("q2_fare", data["q2_fare"]))
    if "q3_comparison" in data:
        compared = rush_differences(detail_rows(data["q3_comparison"]))
        selected = compared[compared.distance_bucket.eq(distance)]
        figure = px.bar(selected, x="Extra minutes", y="borough", orientation="h",
                         title="Rush-hour duration gap · " + str(distance),
                         labels={"borough": "Pickup borough"}, color_discrete_sequence=COLORS)
        figure.add_vline(x=0, line_width=1, line_color="#657487")
        show(figure, False, "overview_rush")
        st.caption(insight("q3_comparison", selected) + " Observed difference, not causation.")
