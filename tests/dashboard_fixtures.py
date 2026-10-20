"""Explicitly synthetic saved exports for UI checks; never warehouse findings."""

from contextlib import contextmanager
from pathlib import Path
import tempfile
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from dashboard import snapshots
from dashboard.config import ROOT
from dashboard.reports import REPORTS
from dashboard.sample_data import sample_result


@contextmanager
def saved_fixtures():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for report in REPORTS:
            data = sample_result(report.id)
            prefix = snapshots.EXPORT_NAMES[report.id]
            path = root / f"{prefix}_20261020_120000_000000.tsv"
            data.to_csv(path, sep="\t", index=False, na_rep="\\N")
            path.with_suffix(".log").write_text(f"SUCCESS\nReport: {prefix}\nRows: {len(data)}\nElapsed seconds: 1\n", encoding="utf-8")
        with patch.object(snapshots, "RESULTS", root):
            yield root


def start_app():
    return AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=30).run()


def select_report(app, section, report_id):
    # AppTest.switch_page supports files only; select callable pages using
    # their registered identity in the same multipage runner.
    app._page_hash = next(page_hash for page_hash, page in app._registered_pages.items()
                          if page.get("url_pathname") == report_id)
    return app.run()
