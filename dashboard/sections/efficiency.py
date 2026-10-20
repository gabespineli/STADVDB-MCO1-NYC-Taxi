from dashboard.sections.common import render_saved

TITLE = "Q3 — Rush-Hour Travel Efficiency"
DESCRIPTION = "Compare travel duration and estimated speed at each reported group."


def render(report, result):
    render_saved(report, result)
