"""Dashboard contracts and UI checks; database operations are mocked."""

import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from dashboard import charts, db, reports
from dashboard.config import DatabaseSettings, ROOT, WAREHOUSE_TABLES, database_settings
from dashboard.sample_data import sample_result


def ready_state():
    return {"connected": True, "tables": {name: "Has records" for name in WAREHOUSE_TABLES},
            "time_periods": ["Late Night", "Morning Rush", "Evening Rush"],
            "locations": [], "placeholder_locations": False, "read_only_account": True}


class ReportContractTests(unittest.TestCase):
    def test_all_seven_fixtures_match_existing_output_contracts(self):
        self.assertEqual(len(reports.REPORTS), 7)
        for report in reports.REPORTS:
            with self.subTest(report=report.id):
                data = reports.validate_result(report, sample_result(report.id))
                self.assertFalse(data.empty)
                self.assertEqual(set(data.columns), set(report.columns))

    def test_sample_additive_counts_reconcile_without_overlapping_series(self):
        demand = sample_result("q1_demand")
        self.assertTrue((demand.total_filtered_pickups == demand.weekday_late_night_pickups + demand.all_weekend_pickups).all())
        self.assertTrue((demand.weekend_late_night_pickups <= demand.all_weekend_pickups).all())
        fare = sample_result("q2_fare")
        self.assertTrue((fare.total_trips == fare.credit_card_trips + fare.cash_trips + fare.other_payment_trips).all())

    def test_existing_student_queries_pass_read_only_guard_unchanged(self):
        statements = [statement for statement in (ROOT / "olap_queries.sql").read_text().split(";") if statement.strip()]
        self.assertEqual(len(statements), 7)
        for statement in statements:
            reports.validate_read_only_sql(statement)

    def test_write_export_multistatement_and_source_queries_are_refused(self):
        cases = ["DELETE FROM fact_trip_records", "SELECT 1; SELECT 2", "SELECT 1 INTO OUTFILE 'x'",
                 "SELECT * FROM yellow_taxi_trips", "SELECT * FROM source_db.fact_trip_records",
                 "SELECT GET_LOCK('x', 0)", "SELECT 1 /*! INTO OUTFILE 'x' */",
                 "SELECT f.trip_id FROM fact_trip_records f, yellow_taxi_trips r"]
        for sql in cases:
            with self.subTest(sql=sql):
                with self.assertRaises(ValueError):
                    reports.validate_read_only_sql(sql)

    def test_registered_queries_are_exact_approved_statements_and_unapproved_stays_blocked(self):
        source = (ROOT / "olap_queries_optimized.sql").read_bytes()
        statements = reports.split_statements(source.decode("utf-8-sig"))
        for report in reports.REPORTS:
            config = reports.report_config(report.id)
            self.assertEqual(config["source_sha256"], reports.source_fingerprint(source))
            self.assertEqual(reports.approved_sql(report, config), statements[config["statement"] - 1])
            self.assertEqual(config["filters"], {})
            with self.assertRaisesRegex(ValueError, "waiting for validated"):
                reports.approved_sql(report, {**config, "validated": False})
            with self.assertRaisesRegex(ValueError, "file changed"):
                reports.approved_sql(report, {**config, "source_sha256": "changed"})

    def test_approved_file_uses_original_statement_and_checks_all_bindings(self):
        original = (ROOT / "olap_queries.sql").read_text().split(";")[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "queries").mkdir()
            (root / "queries" / "report.sql").write_text(original)
            config = {"validated": True, "aggregated": True, "sql_file": "report.sql",
                      "population": "Test-only approval metadata", "grain": "zone", "filters": {}}
            with patch.object(reports, "HERE", root):
                self.assertEqual(reports.approved_sql(reports.REPORTS[0], config), original)
                with self.assertRaisesRegex(ValueError, "bind parameters"):
                    reports.approved_sql(reports.REPORTS[0], {**config, "filters": {"borough": "borough"}})
                with self.assertRaises(ValueError):
                    reports.approved_sql(reports.REPORTS[0], {**config, "sql_file": "../outside.sql"})
                with self.assertRaises(ValueError):
                    reports.approved_sql(reports.REPORTS[0], {**config, "population": ""})

    def test_missing_and_nonnumeric_results_fail_but_nulls_are_retained(self):
        report = reports.REPORTS[0]
        data = sample_result(report.id)
        with self.assertRaisesRegex(ValueError, "missing columns"):
            reports.validate_result(report, data.drop(columns="zone"))
        broken = data.copy()
        broken["total_filtered_pickups"] = "invalid"
        with self.assertRaisesRegex(ValueError, "must contain numbers"):
            reports.validate_result(report, broken)
        data["total_filtered_pickups"] = None
        self.assertTrue(reports.validate_result(report, data).total_filtered_pickups.isna().all())

    def test_rollup_rows_are_not_added_to_detail_counts(self):
        data = sample_result("q1_demand")
        total = data.iloc[[0]].copy()
        total["borough"], total["zone"] = "ALL BOROUGHS", "Borough Subtotal"
        detail = charts.detail_rows(pd.concat([data, total], ignore_index=True))
        self.assertEqual(len(detail), len(data))

    def test_live_reports_require_complete_dimensions_and_semantic_labels(self):
        state = ready_state()
        self.assertEqual(reports.live_blockers(reports.REPORTS[0], state), [])
        state["time_periods"] = ["Morning", "Night"]
        self.assertTrue(reports.live_blockers(reports.REPORTS[0], state))
        state = ready_state()
        state["placeholder_locations"] = True
        self.assertTrue(reports.live_blockers(reports.REPORTS[0], state))
        self.assertEqual(reports.live_blockers(reports.REPORTS[3], state), [])
        state["tables"].pop("dim_date")
        self.assertTrue(reports.live_blockers(reports.REPORTS[3], state))


class DatabaseTests(unittest.TestCase):
    def test_credentials_are_not_in_repr_and_environment_overrides_dotenv(self):
        with patch("dashboard.config.dotenv_values", return_value={"DB_USER": "file-user", "DB_PASSWORD": "private"}), patch.dict("os.environ", {"DASHBOARD_DB_USER": "reader"}, clear=True):
            settings = database_settings()
            self.assertEqual(settings.user, "reader")
            self.assertEqual(settings.password, "private")
            self.assertNotIn("private", repr(settings))

    def test_read_connection_starts_read_only_and_rolls_back_on_failure(self):
        engine = MagicMock()
        connection = engine.connect.return_value.__enter__.return_value
        with patch.object(db, "get_engine", return_value=engine):
            with self.assertRaises(ValueError):
                with db.read_connection(DatabaseSettings("reader", "secret")):
                    raise ValueError("synthetic failure")
        connection.exec_driver_sql.assert_called_once_with("START TRANSACTION READ ONLY")
        connection.rollback.assert_called_once()

    def test_readiness_does_not_count_or_read_raw_trips(self):
        connection = MagicMock()
        existing = MagicMock()
        existing.scalars.return_value = WAREHOUSE_TABLES
        periods = MagicMock()
        periods.scalars.return_value = ["Late Night"]
        locations = MagicMock()
        locations.mappings.return_value = [{"location_id": 1, "zone": "Zone 1", "borough": "Unknown"}]
        found = MagicMock()
        found.first.return_value = (1,)
        connection.execute.side_effect = [MagicMock(), [("GRANT SELECT ON db.* TO 'reader'@'localhost'",)], existing] + [found] * 6 + [periods, locations]
        with patch.object(db, "read_connection", return_value=nullcontext(connection)):
            state = db.warehouse_readiness.__wrapped__(DatabaseSettings("test", "secret"))
        self.assertTrue(state["connected"])
        self.assertTrue(state["placeholder_locations"])
        statements = [str(call.args[0]).upper() for call in connection.execute.call_args_list]
        self.assertFalse(any("COUNT(" in sql or "YELLOW_TAXI_TRIPS" in sql for sql in statements))

    def test_large_results_are_rejected_without_rewriting_sql(self):
        connection = MagicMock()
        result = connection.execution_options.return_value.execute.return_value.__enter__.return_value
        result.keys.return_value = ["value"]
        result.fetchmany.return_value = [(1,), (2,), (3,), (4,)]
        with patch.object(db, "MAX_REPORT_ROWS", 3), patch.object(db, "verified_read_only_account", return_value=True), patch.object(db, "read_connection", return_value=nullcontext(connection)):
            with self.assertRaisesRegex(ValueError, "exceeds 3"):
                db.run_report.__wrapped__(DatabaseSettings("test", "secret"), "diagnostic", "SELECT 1", {})
        self.assertEqual(str(connection.execution_options.return_value.execute.call_args.args[0]), "SELECT 1")


class DashboardAppTests(unittest.TestCase):
    def setUp(self):
        from dashboard_fixtures import saved_fixtures
        self.fixture = saved_fixtures()
        self.folder = self.fixture.__enter__()
        self.addCleanup(self.fixture.__exit__, None, None, None)

    def test_all_seven_saved_reports_render_without_source_controls(self):
        from dashboard_fixtures import start_app, select_report
        with patch.object(db, "warehouse_readiness") as health, patch.object(db, "run_report") as query:
            app = start_app()
            self.assertEqual(app.title[0].value, "Overview")
            self.assertEqual(len(app.sidebar.radio), 0)
            self.assertFalse(any(w.label == "Data source" for w in app.radio))
            for report in reports.REPORTS:
                select_report(app, report.section, report.id)
                self.assertEqual(len(app.exception), 0)
                self.assertGreater(len(app.get("plotly_chart")), 0)
                self.assertFalse(any("SYNTHETIC SAMPLE" in w.value for w in app.warning))
            health.assert_not_called()
            query.assert_not_called()

    def test_missing_exports_never_become_samples_or_database_queries(self):
        from dashboard_fixtures import start_app, select_report
        for path in self.folder.glob("*.log"):
            path.write_text("FAILED\n")
        with patch.object(db, "run_report") as query:
            app = start_app()
            self.assertEqual(len(app.get("plotly_chart")), 0)
            select_report(app, "Q1", "q1_demand")
            self.assertTrue(any("Awaiting a completed export" in x.value for x in app.info))
            self.assertEqual(len(app.get("plotly_chart")), 0)
            query.assert_not_called()

    def test_compact_navigation_and_toolbar(self):
        from dashboard_fixtures import start_app, select_report
        app = select_report(start_app(), "Q1", "q1_hourly")
        self.assertEqual(len(app.sidebar), 0)
        self.assertFalse(any(e.label == "NYC Taxi · 2025" for e in app.expander))
        self.assertEqual(len(app.radio), 0)
        self.assertEqual(app.title[0].value, "Hourly demand trends")
        self.assertEqual(len(app._registered_pages), 8)
        self.assertFalse(any(b.label in ("Load warehouse report", "Refresh from MySQL", "Refresh saved results") for b in app.button))
        self.assertFalse(any("Current view: all returned" in c.value for c in app.caption))

    def test_invalid_saved_output_does_not_show_sample(self):
        from dashboard_fixtures import start_app, select_report
        path = next(self.folder.glob("q1_zone_borough_*.tsv"))
        path.write_text("borough\tzone\nManhattan\tExample\n")
        app = select_report(start_app(), "Q1", "q1_demand")
        self.assertGreater(len(app.error), 0)
        self.assertEqual(len(app.get("plotly_chart")), 0)


if __name__ == "__main__":
    unittest.main()
