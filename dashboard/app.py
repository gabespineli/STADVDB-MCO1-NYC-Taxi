"""Run from the repository: python -m streamlit run dashboard/app.py"""

import sys
import uuid
from pathlib import Path

# Streamlit also supports execution when its script directory is on sys.path.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from dashboard import db
from dashboard.config import database_settings
from dashboard.filters import render_filters
from dashboard.reports import REPORTS, approved_sql, live_blockers, report_config, validate_result
from dashboard.sample_data import sample_result
from dashboard.snapshots import completed_exports, load_export
from dashboard.sections.common import render_saved
from dashboard.sections import demand, efficiency, payments

SECTIONS = {"Q1": demand, "Q2": payments, "Q3": efficiency}


def main():
    st.set_page_config(page_title="NYC Yellow Taxi Analytics — 2025", page_icon="🚕", layout="wide")
    st.markdown("<style>" + (Path(__file__).parent / "style.css").read_text() + "</style>", unsafe_allow_html=True)
    st.title("NYC Yellow Taxi Analytics — 2025")

    exports = {report.id: completed_exports(report.id) for report in REPORTS}
    available = sum(bool(items) for items in exports.values())
    default_section = next((report.section for report in REPORTS if exports[report.id]), "Q1")
    settings = None
    readiness = {"connected": False, "tables": {}, "locations": [], "time_periods": []}
    with st.sidebar:
        st.header("Reports")
        section = st.radio("Section", list(SECTIONS),
                           index=list(SECTIONS).index(default_section),
                           format_func=lambda key: {"Q1": "Q1 · Demand", "Q2": "Q2 · Payments", "Q3": "Q3 · Efficiency"}[key])
        mode = st.radio("Data source", ["Saved exports", "Warehouse reports", "Sample preview"])
        if mode == "Saved exports":
            st.caption(f"{available} / 7 reports available")
            if st.button("Refresh saved results", width="stretch"):
                load_export.clear()
                st.rerun()
        if mode == "Warehouse reports":
            st.divider()
            try:
                settings = database_settings()
                with st.spinner("Connecting…"):
                    readiness = db.warehouse_readiness(settings)
            except ValueError as error:
                readiness["error"] = str(error)
            if readiness.get("error"):
                st.warning(readiness["error"])
            elif readiness.get("connected"):
                st.caption("MySQL connected")
            with st.expander("Connection details"):
                if st.button("Refresh database status"):
                    db.warehouse_readiness.clear()
                    st.rerun()
                for table, status in readiness["tables"].items():
                    st.write(f"{table}: {status}")

    module = SECTIONS[section]
    st.header(module.TITLE)
    section_reports = {item.id: item for item in REPORTS if item.section == section}
    choices = list(section_reports)
    preferred = next((index for index, key in enumerate(choices) if exports[key]), 0)
    report_id = st.selectbox("Report", choices, index=preferred, key=f"report_{section}",
                             format_func=lambda key: section_reports[key].title)
    report = section_reports[report_id]
    if mode == "Saved exports":
        choices = exports[report.id]
        if not choices:
            st.info("Awaiting a completed export for this report.")
            return
        selection = 0
        if len(choices) > 1:
            selection = st.selectbox("Saved run", range(len(choices)),
                                     format_func=lambda i: choices[i].exported_at + f" · {choices[i].rows:,} result groups",
                                     key=f"saved_run_{report.id}")
        try:
            with st.spinner("Opening saved results…"):
                result = load_export(report, choices[selection])
            render_saved(report, result)
        except ValueError as error:
            st.error(str(error))
        return
    try:
        config = report_config(report.id)
    except ValueError as error:
        st.error(str(error))
        return
    sql, approval_error = None, None
    try:
        sql = approved_sql(report, config)
    except ValueError as error:
        approval_error = str(error)
    sample = mode == "Sample preview"
    blockers = live_blockers(report, readiness)
    enabled = not sample and sql is not None and not blockers
    if not sample:
        if approval_error:
            st.info(approval_error)
        for blocker in blockers:
            st.warning(blocker)
        seconds = config.get("benchmark_seconds")
        if seconds is not None:
            st.caption(f"Recorded runtime · {seconds / 60:.1f} min")
    submitted, parameters = (False, {}) if sample else render_filters(report, config, readiness, enabled)
    refresh = (st.button("Refresh from MySQL", disabled=not enabled,
                         help="Executes this report again, even when cached. This may take up to approximately 49 minutes.")
               if not sample else False)

    if sample:
        module.render(report, validate_result(report, sample_result(report.id)), sample=True)
        return
    if not enabled:
        st.info("This report is not ready to load.")
        return
    result_key = "warehouse_result_" + report.id
    # A changed SQL/configuration/filter selection cannot display a previous result.
    signature = (settings, sql, tuple(sorted(parameters.items())), config.get("population"), config.get("grain"))
    if submitted or refresh:
        st.session_state.pop(result_key, None)
        try:
            if refresh:
                db.run_report.clear(settings, report.id, sql, parameters)
            request_id = uuid.uuid4().hex
            with st.spinner("Running report…", show_time=True):
                result = db.run_report(settings, report.id, sql, parameters, _request_id=request_id)
                result["data"] = validate_result(report, result["data"])
                result["cache_hit"] = result.get("execution_id") != request_id
                st.session_state[result_key] = {"signature": signature, "result": result}
        except (db.DatabaseError, ValueError) as error:
            st.error(str(error))
    stored = st.session_state.get(result_key)
    if stored and stored["signature"] == signature:
        result = stored["result"]
        module.render(report, result["data"], sample=False, fetched_at=result["fetched_at"], parameters=parameters,
                      cache_hit=result.get("cache_hit", False), seconds=result.get("seconds"))
    elif not submitted and not refresh:
        st.info("Select Load warehouse report to view results.")


if __name__ == "__main__":
    main()
