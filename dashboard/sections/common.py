"""Report presentation with a compact toolbar and saved-export data."""

import streamlit as st

from dashboard.charts import render_charts
from dashboard.controls import chart_options
from dashboard.filters import render_saved_filters
from dashboard.presentation import CAUTIONS, SCOPES, SHORT_NOTES, insight, render_context


def render_saved(report, result):
    data = result["data"]
    if data.empty:
        st.info("No result rows.")
        return
    adjust, source, _ = st.columns([1.5, 1, 7.5])
    with adjust:
        with st.popover("Adjust view", icon=":material/tune:", width="stretch"):
            filtered, selections, minimum = render_saved_filters(report, data, result["sha256"])
            options = chart_options(report.id, filtered)
    with source:
        with st.popover("Data", icon=":material/table_view:", width="stretch"):
            st.caption(SCOPES[report.id])
            st.dataframe(filtered, width="stretch", hide_index=True)
            st.download_button("Download CSV", filtered.to_csv(index=False, na_rep="\\N").encode("utf-8-sig"),
                               file_name=f"{report.id}_filtered.csv", mime="text/csv")
            st.caption(CAUTIONS[report.id])
            st.caption("Charts may show a ranked or selected subset. This CSV includes every group selected by the filters.")
            if report.id == "q3_location":
                extremes = filtered[(filtered.avg_speed_mph > 100) | (filtered.avg_duration_minutes > 120)]
                if len(extremes):
                    with st.expander("Flagged groups"):
                        st.caption("Mean speed >100 mph or mean duration >120 minutes. No rows removed.")
                        st.dataframe(extremes, hide_index=True, width="stretch")
            with st.expander("Source and complete output"):
                st.caption(f"{result['exported_at']} · {len(data):,} original rows")
                st.text(result["filename"])
                st.write(report.note)
                st.download_button("Download complete export", data.to_csv(index=False, sep="\t", na_rep="\\N").encode("utf-8-sig"),
                                   file_name=result["filename"], mime="text/tab-separated-values")
    if filtered.empty:
        st.info("No matching groups. Reset the view in Adjust view.")
        return
    render_context(report, filtered, selections, minimum)
    finding = insight(report.id, filtered)
    if finding:
        st.caption(finding)
    render_charts(report.id, filtered, False, options)
    note = SHORT_NOTES[report.id]
    if report.id == "q3_location":
        extremes = int(((filtered.avg_speed_mph > 100) | (filtered.avg_duration_minutes > 120)).sum())
        small = int((filtered.trip_count < 30).sum())
        note = f"{extremes:,} flagged groups · {small:,} groups below 30 trips. " + note
    st.caption(note)
