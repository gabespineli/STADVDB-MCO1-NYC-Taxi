from dashboard.sections.common import render_result

TITLE = "Q3 — Rush-Hour Travel Efficiency"
DESCRIPTION = "Compare travel duration and estimated speed at each reported group."


def render(report, data, **context):
    render_result(report, data, **context)
