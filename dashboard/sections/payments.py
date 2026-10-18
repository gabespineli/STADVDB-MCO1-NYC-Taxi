from dashboard.sections.common import render_result

TITLE = "Q2 — Payment and Fare Patterns"
DESCRIPTION = "Explore recorded payment composition and fare patterns."


def render(report, data, **context):
    render_result(report, data, **context)
