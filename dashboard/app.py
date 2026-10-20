"""Saved-export dashboard with query navigation in Streamlit's native header."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from dashboard.reports import REPORTS
from dashboard.snapshots import completed_exports, load_export
from dashboard.sections.common import render_saved
from dashboard.sections import overview

LABELS = {"Q1": "Q1 · Demand", "Q2": "Q2 · Payments", "Q3": "Q3 · Travel"}


def render_report(report):
    st.title(report.title)
    runs = completed_exports(report.id)
    if not runs:
        st.info("Awaiting a completed export for this report.")
        return
    try:
        render_saved(report, load_export(report, runs[0]))
    except ValueError as error:
        st.error(str(error))


def render_overview():
    st.title("Overview")
    overview.render({report.id: completed_exports(report.id) for report in REPORTS})


def main():
    st.set_page_config(page_title="NYC Taxi | 2025", page_icon=":material/local_taxi:", layout="wide", initial_sidebar_state="collapsed")
    st.markdown("<style>" + (Path(__file__).parent / "style.css").read_text(encoding="utf-8") + "</style>", unsafe_allow_html=True)
    pages = {"": [st.Page(render_overview, title="Overview", default=True)]}
    for section, label in LABELS.items():
        pages[label] = [
            st.Page(lambda report=report: render_report(report),
                    title=report.title, url_path=report.id)
            for report in REPORTS if report.section == section
        ]
    st.navigation(pages, position="top").run()


if __name__ == "__main__":
    main()
