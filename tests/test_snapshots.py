"""Saved exports must be complete, truthful, and browseable without MySQL."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from dashboard import db, snapshots
from dashboard.config import ROOT
from dashboard.filters import filter_saved_rows
from dashboard.reports import REPORTS

REPORT = next(report for report in REPORTS if report.id == "q3_location")


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.path = self.folder / "q3_midrange_20261018_215558_577398.tsv"
        self.data = pd.DataFrame([
            ["Manhattan", "Midtown", "Morning Rush", 8, 100, 3, 15, 12],
            ["N/A", "Outside of NYC", "Late Night", 2, 2, 4, 10, 150],
        ], columns=REPORT.columns)
        self.data.to_csv(self.path, sep="\t", index=False, encoding="utf-8-sig")
        self.path.with_suffix(".log").write_text("SUCCESS\nReport: q3_midrange\nRows: 2\nElapsed seconds: 453.29\n", encoding="utf-8")

    def test_partial_failed_and_unpaired_exports_are_never_available(self):
        (self.folder / "q3_midrange_20261019_000000_000000.partial.tsv").write_text("partial")
        failed = self.folder / "q3_midrange_20261019_000001_000000.tsv"
        failed.write_text("failed")
        failed.with_suffix(".log").write_text("FAILED\n")
        (self.folder / "q3_midrange_20261019_000002_000000.tsv").write_text("unpaired")
        self.assertEqual(len(snapshots.completed_exports(REPORT.id, self.folder)), 1)

    def test_lookup_na_is_preserved_and_null_speed_is_not_zero(self):
        self.data.loc[1, "avg_speed_mph"] = float("nan")
        self.data.to_csv(self.path, sep="\t", na_rep="\\N", index=False)
        export = snapshots.completed_exports(REPORT.id, self.folder)[0]
        result = snapshots.load_export.__wrapped__(REPORT, export)
        self.assertEqual(result["data"].iloc[1].borough, "N/A")
        self.assertTrue(pd.isna(result["data"].iloc[1].avg_speed_mph))

    def test_mismatched_log_and_duplicate_groups_are_rejected(self):
        self.path.with_suffix(".log").write_text("SUCCESS\nReport: q3_midrange\nRows: 3\nElapsed seconds: 1\n")
        export = snapshots.completed_exports(REPORT.id, self.folder)[0]
        with self.assertRaisesRegex(ValueError, "row count"):
            snapshots.load_export.__wrapped__(REPORT, export)
        pd.concat([self.data, self.data.iloc[[0]]]).to_csv(self.path, sep="\t", index=False)
        export = snapshots.completed_exports(REPORT.id, self.folder)[0]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            snapshots.load_export.__wrapped__(REPORT, export)

    def test_filters_preserve_original_group_averages(self):
        selected = filter_saved_rows(self.data, {"borough": "Manhattan", "hour": list(range(6, 10))}, 30)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected.iloc[0].avg_speed_mph, 12)
        self.assertEqual(len(filter_saved_rows(self.data, {})), 2)

    def test_snapshot_default_never_connects_to_mysql_and_filters_reset(self):
        from dashboard_fixtures import select_report
        with patch.object(snapshots, "RESULTS", self.folder), patch.object(db, "warehouse_readiness") as health, patch.object(db, "run_report") as query:
            app = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=30).run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.sidebar.radio), 0)
            self.assertEqual(app.title[0].value, "Overview")
            self.assertEqual(app.metric[0].value, "Unavailable")
            select_report(app, "Q3", "q3_location")
            self.assertEqual(app.metric[0].value, "102")
            next(widget for widget in app.selectbox if widget.label == "Borough").set_value("Manhattan").run()
            self.assertEqual(app.metric[0].value, "100")
            next(button for button in app.button if button.label == "Reset view").click().run()
            self.assertEqual(app.metric[0].value, "102")
            self.assertIsNone(next(widget for widget in app.selectbox if widget.label == "Borough").value)
            select_report(app, "Q1", "q1_demand")
            self.assertTrue(any("Awaiting a completed export" in info.value for info in app.info))
            self.assertEqual(len(app.get("plotly_chart")), 0)
            health.assert_not_called()
            query.assert_not_called()


if __name__ == "__main__":
    unittest.main()
