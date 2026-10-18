from dashboard.sections.common import render_result

TITLE = "Q1 — Late-Night and Weekend Demand"
DESCRIPTION = "Compare pickup demand across locations, hours, and months."


def render(report, data, **context):
    render_result(report, data, **context)
