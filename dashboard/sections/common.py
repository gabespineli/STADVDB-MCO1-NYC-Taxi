import streamlit as st

from dashboard.charts import render_charts


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
