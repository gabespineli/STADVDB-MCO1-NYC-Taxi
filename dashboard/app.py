"""Run from the repository: python -m streamlit run dashboard/app.py"""

import sys
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
        st.header("Explore the warehouse")
        section = st.radio("Analytical section", list(SECTIONS),
                           index=list(SECTIONS).index(default_section),
                           format_func=lambda key: {"Q1": "Q1 · Demand", "Q2": "Q2 · Payments", "Q3": "Q3 · Efficiency"}[key])
        mode = st.radio("Data source", ["Saved exports", "Sample preview", "Warehouse reports"],
                        help="Saved exports open immediately without querying MySQL. Sample previews use synthetic data.")
        if mode == "Saved exports":
            st.caption(f"{available} of 7 reports have completed exports.")
            if st.button("Refresh saved results", width="stretch"):
                load_export.clear()
                st.rerun()
            with st.expander("Add your teammate’s results"):
                st.write("Copy a compatible completed .tsv and matching SUCCESS .log into dashboard/exports, then refresh saved results.")
                st.caption("Use the export format described in dashboard/exports/README.md. Failed and partial files are ignored. Export success is not analytical approval.")
        if mode == "Warehouse reports":
            st.divider()
            st.subheader("Database availability")
            try:
                settings = database_settings()
                with st.spinner("Checking warehouse availability…"):
                    readiness = db.warehouse_readiness(settings)
            except ValueError as error:
                readiness["error"] = str(error)
            if readiness.get("error"):
                st.warning(readiness["error"])
            elif readiness.get("connected"):
                st.success("MySQL connected")
            if st.button("Refresh database status"):
                db.warehouse_readiness.clear()
                st.rerun()
            with st.expander("Table checks"):
                for table, status in readiness["tables"].items():
                    st.write(f"{table}: {status}")
                st.caption("Presence checks do not validate ETL or execute reports.")

    module = SECTIONS[section]
    st.header(module.TITLE)
    st.caption(module.DESCRIPTION)
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
            st.write("Your teammate can run this report separately and provide the TSV and matching completion log. No database query has been started.")
            st.caption("Use Sample preview in the sidebar to explore its layout with clearly labeled synthetic data.")
            with st.expander("Saved report availability"):
                for item in REPORTS:
                    st.write(f"{item.section} · {item.title}: {'Available' if exports[item.id] else 'Awaiting export'}")
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
            st.info(approval_error + ". Sample preview remains available in the sidebar.")
        for blocker in blockers:
            st.warning(blocker)
    submitted, parameters = render_filters(report, config, readiness, enabled)

    with st.expander("Report definition and integration status"):
        st.write("SQL status: " + ("Validated" if sql else "Awaiting OLAP teammate validation"))
        st.write("Population: " + (config.get("population") or "Awaiting the group's approved 2025 population"))
        st.write("Result grain: " + (config.get("grain") or "Awaiting validation"))
        st.caption("Expected result columns: " + ", ".join(report.columns))
        st.caption("The existing analytical SQL is not executed automatically. Student-authored SQL is connected through dashboard/reports.json.")

    if sample:
        module.render(report, validate_result(report, sample_result(report.id)), sample=True)
        return
    if not enabled:
        st.info("This warehouse report is not ready to load. No sample values are displayed in warehouse mode.")
        return
    result_key = "warehouse_result_" + report.id
    # A changed SQL/configuration/filter selection cannot display a previous result.
    signature = (settings, sql, tuple(sorted(parameters.items())), config.get("population"), config.get("grain"))
    if submitted:
        st.session_state.pop(result_key, None)
        try:
            with st.spinner("Loading aggregated warehouse results…"):
                result = db.run_report(settings, report.id, sql, parameters)
                result["data"] = validate_result(report, result["data"])
                st.session_state[result_key] = {"signature": signature, "result": result}
        except (db.DatabaseError, ValueError) as error:
            st.error(str(error))
    stored = st.session_state.get(result_key)
    if stored and stored["signature"] == signature:
        result = stored["result"]
        module.render(report, result["data"], sample=False, fetched_at=result["fetched_at"], parameters=parameters)
    elif not submitted:
        st.info("Select Load warehouse report to run the approved aggregated query for these filters.")


if __name__ == "__main__":
    main()
