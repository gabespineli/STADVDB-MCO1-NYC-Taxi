import streamlit as st

from dashboard.charts import render_charts


def render_saved(report, result):
    from dashboard.charts import detail_rows
    from dashboard.filters import render_saved_filters

    st.caption(f"Saved warehouse export · {result['exported_at']} (filename, local time) · Analytical review pending")
    data = result["data"]
    if data.empty:
        st.info("This completed export contains no result rows.")
        return
    filtered, selections, minimum = render_saved_filters(report, data, result["sha256"])
    if report.id != "q3_location":
        st.caption(report.note)
    if filtered.empty:
        st.info("No result groups match these filters. Reset the view or choose a lower minimum trip count.")
        return
    stats = st.columns(3)
    stats[0].metric("Result groups shown", f"{len(filtered):,}")
    count = next((name for name in ("trip_count", "total_filtered_pickups", "total_trips", "late_night_pickups") if name in filtered), None)
    if count:
        stats[1].metric("Trips represented", f"{filtered[count].sum():,.0f}")
    elif report.id == "q1_hourly":
        stats[1].metric("Pickups represented", f"{filtered[['weekday_pickups', 'weekend_pickups']].sum().sum():,.0f}")
    else:
        stats[1].metric("Boroughs shown", str(filtered.borough.nunique()) if "borough" in filtered else "—")
    stats[2].metric("Original query runtime", f"{result['seconds'] / 60:.1f} min")
    if report.id == "q3_location":
        extremes = filtered[(filtered.avg_speed_mph > 100) | (filtered.avg_duration_minutes > 120)]
        small = int((filtered.trip_count < 30).sum())
        if len(extremes):
            st.warning(f"{len(extremes):,} visible groups have mean speed above 100 mph or mean duration above 120 minutes. These are review flags; no outliers have been removed.")
        if small:
            st.caption(f"{small:,} visible groups contain fewer than 30 trips. Use the minimum-trip control to inspect larger groups; 30 is an exploration threshold, not a statistical guarantee.")
        render_charts(report.id, filtered, False)
        if len(extremes):
            with st.expander("Inspect flagged result groups"):
                st.dataframe(extremes.sort_values("avg_speed_mph", ascending=False), width="stretch", hide_index=True)
    else:
        render_charts(report.id, filtered, False)
    with st.expander("Detailed results and download"):
        st.caption("These are the same filtered groups used by the charts. SQL subtotal rows are excluded from this view.")
        st.dataframe(filtered, width="stretch", hide_index=True)
        st.download_button("Download filtered results", filtered.to_csv(index=False, na_rep="\\N").encode("utf-8-sig"),
                           file_name=f"{report.id}_filtered.csv", mime="text/csv")
    with st.expander("Source, definitions, and complete export"):
        st.write(f"Source file: {result['filename']}")
        st.caption("Browsing and filtering this saved export does not connect to MySQL.")
        st.write(f"Original export: {len(data):,} rows · {len(detail_rows(data)):,} detail groups")
        st.caption("A SUCCESS log confirms completed execution, not independent analytical approval. Rates and means remain at the SQL's original grain; they are never averaged together.")
        if report.id == "q3_location":
            st.write("Population: weekday pickups, distance 2–5 miles inclusive, positive duration. Each row is a pickup borough × zone × period × hour group across the reporting population.")
            st.caption("Speed is the mean of individual estimated trip speeds, not mean distance divided by mean duration. EWR, N/A, and Unknown are retained lookup categories. Month/date filtering is unavailable because this export does not contain those fields.")
        st.caption("File fingerprint (SHA-256): " + result["sha256"])
        st.download_button("Download complete export", data.to_csv(index=False, sep="\t", na_rep="\\N").encode("utf-8-sig"),
                           file_name=result["filename"], mime="text/tab-separated-values")


def render_result(report, data, sample, fetched_at=None, parameters=None):
    if sample:
        st.warning("SYNTHETIC SAMPLE — Layout demonstration only. These values are not NYC Taxi findings.")
        st.caption("Each sample report is an independent fixture. Sample time labels do not define the group's time boundaries.")
    else:
        st.success("Warehouse result · validated SQL")
        st.caption(f"Fetched at {fetched_at} · UTC. The result may be served from the five-minute cache.")
        if parameters:
            st.caption("Applied SQL parameters: " + ", ".join(f"{key}={value}" for key, value in parameters.items()))
    st.caption(report.note)
    if data.empty:
        st.info("The query returned no rows for this selection. No sample data has been substituted.")
        return
    render_charts(report.id, data, sample)
    with st.expander("Detailed results · includes any SQL rollup rows", expanded=False):
        st.caption(f"{len(data):,} aggregated result rows. Chart rollups are excluded to avoid double counting.")
        st.dataframe(data, width="stretch", hide_index=True)
        exported = data.copy()
        exported.insert(0, "data_classification", "SYNTHETIC SAMPLE — NOT OBSERVED" if sample else "WAREHOUSE RESULT")
        st.download_button("Download result CSV", data=exported.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"{report.id}_{'SAMPLE' if sample else 'warehouse'}.csv", mime="text/csv")
