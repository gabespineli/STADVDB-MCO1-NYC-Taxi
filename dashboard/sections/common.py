import streamlit as st

from dashboard.charts import render_charts


def render_saved(report, result):
    from dashboard.charts import detail_rows
    from dashboard.filters import render_saved_filters

    st.caption(f"Saved results · {result['exported_at']}")
    data = result["data"]
    if data.empty:
        st.info("No result rows.")
        return
    filtered, selections, minimum = render_saved_filters(report, data, result["sha256"])
    if filtered.empty:
        st.info("No matching groups. Reset the filters to see all results.")
        return
    stats = st.columns(2)
    stats[0].metric("Result groups", f"{len(filtered):,}")
    count = next((name for name in ("trip_count", "total_filtered_pickups", "total_trips", "late_night_pickups") if name in filtered), None)
    if count:
        stats[1].metric("Trips represented", f"{filtered[count].sum():,.0f}")
    elif report.id == "q1_hourly":
        stats[1].metric("Pickups represented", f"{filtered[['weekday_pickups', 'weekend_pickups']].sum().sum():,.0f}")
    else:
        stats[1].metric("Boroughs shown", str(filtered.borough.nunique()) if "borough" in filtered else "—")
    if report.id == "q3_location":
        extremes = filtered[(filtered.avg_speed_mph > 100) | (filtered.avg_duration_minutes > 120)]
        small = int((filtered.trip_count < 30).sum())
        if len(extremes):
            st.warning(f"{len(extremes):,} groups flagged: mean speed >100 mph or duration >120 min. No rows removed.")
        render_charts(report.id, filtered, False)
        if len(extremes):
            with st.expander("Inspect flagged result groups"):
                if small:
                    st.caption(f"{small:,} groups have fewer than 30 trips.")
                st.dataframe(extremes.sort_values("avg_speed_mph", ascending=False), width="stretch", hide_index=True)
    else:
        render_charts(report.id, filtered, False)
    with st.expander("Detailed results and download"):
        st.caption(f"{len(filtered):,} displayed groups · subtotals excluded")
        st.dataframe(filtered, width="stretch", hide_index=True)
        st.download_button("Download filtered results", filtered.to_csv(index=False, na_rep="\\N").encode("utf-8-sig"),
                           file_name=f"{report.id}_filtered.csv", mime="text/csv")
    with st.expander("Report details"):
        st.write(f"Source file: {result['filename']}")
        st.caption(f"{len(data):,} rows · {len(detail_rows(data)):,} detail groups · recorded runtime {result['seconds'] / 60:.1f} min")
        st.write(report.note)
        if report.id == "q3_location":
            st.caption("Speed is the mean of individual trip speeds. EWR, N/A, and Unknown are retained.")
        st.download_button("Download complete export", data.to_csv(index=False, sep="\t", na_rep="\\N").encode("utf-8-sig"),
                           file_name=result["filename"], mime="text/tab-separated-values")


def render_result(report, data, sample, fetched_at=None, parameters=None, cache_hit=False, seconds=None):
    if sample:
        st.warning("SYNTHETIC SAMPLE — Not actual taxi data.")
    else:
        source = "Cached database result" if cache_hit else "Freshly retrieved from MySQL"
        st.caption(f"{source} · {fetched_at} UTC")
        if parameters:
            st.caption("Applied SQL parameters: " + ", ".join(f"{key}={value}" for key, value in parameters.items()))
    if data.empty:
        st.info("The query returned no rows.")
        return
    # Browsing returned groups is explicitly separate from SQL parameterization.
    shown = data
    if not sample:
        from dashboard.filters import render_saved_filters
        shown, _, _ = render_saved_filters(report, data, "live_" + str(fetched_at))
        if shown.empty:
            st.info("No matching groups. Reset the filters to see all results.")
    render_charts(report.id, shown, sample)
    with st.expander("Results and download", expanded=False):
        st.caption(f"{len(shown):,} result groups")
        st.dataframe(shown, width="stretch", hide_index=True)
        exported = shown.copy()
        exported.insert(0, "data_classification", "SYNTHETIC SAMPLE — NOT OBSERVED" if sample else "WAREHOUSE RESULT")
        st.download_button("Download result CSV", data=exported.to_csv(index=False, na_rep="\\N").encode("utf-8-sig"),
                           file_name=f"{report.id}_{'SAMPLE' if sample else 'warehouse'}.csv", mime="text/csv")
    if not sample:
        with st.expander("Report details and complete output"):
            st.write(report.note)
            if seconds is not None:
                st.caption(f"Retrieval time · {seconds:,.2f} s")
            st.caption("Complete output includes subtotals and totals.")
            st.dataframe(data, width="stretch", hide_index=True)
            st.download_button("Download complete SQL output", data.to_csv(index=False, na_rep="\\N").encode("utf-8-sig"),
                               file_name=f"{report.id}_complete_warehouse.csv", mime="text/csv")
