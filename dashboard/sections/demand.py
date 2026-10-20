from dashboard.sections.common import render_saved

TITLE = "Q1 — Late-Night and Weekend Demand"
DESCRIPTION = "Compare pickup demand across locations, hours, and months."


def render(report, result):
    render_saved(report, result)
