"""Application integration only: no full warehouse reports are executed."""

from contextlib import nullcontext
from io import BytesIO
import threading
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from dashboard import db, reports
from dashboard.config import DatabaseSettings, ROOT, database_settings
from dashboard.sample_data import sample_result
from test_dashboard import ready_state


class IntegratedDatabaseTests(unittest.TestCase):
    def tearDown(self):
        db.run_report.clear()

    def connection(self):
        connection = MagicMock()
        result = connection.execution_options.return_value.execute.return_value.__enter__.return_value
        result.keys.return_value = ["value"]
        result.fetchmany.return_value = [(7,)]
        return connection

    def test_cache_exact_sql_parameters_identity_and_targeted_refresh(self):
        db.run_report.clear()
        connection = self.connection()
        settings = DatabaseSettings("reader", "not-a-real-password")
        with patch.object(db, "read_connection", side_effect=lambda _: nullcontext(connection)) as read, patch.object(db, "verified_read_only_account", return_value=True):
            first = db.run_report(settings, "diagnostic", "SELECT 7", {}, _request_id="first")
            cached = db.run_report(settings, "diagnostic", "SELECT 7", {}, _request_id="second")
            self.assertEqual(read.call_count, 1)
            self.assertEqual(cached["execution_id"], "first")
            self.assertEqual(first["data"].iloc[0, 0], 7)
            db.run_report(settings, "diagnostic", "SELECT 7", {"approved_value": 1}, _request_id="different-params")
            db.run_report(settings, "diagnostic", "SELECT 8", {}, _request_id="different-sql")
            self.assertEqual(read.call_count, 3)
            db.run_report.clear(settings, "diagnostic", "SELECT 7", {})
            refreshed = db.run_report(settings, "diagnostic", "SELECT 7", {}, _request_id="refresh")
            self.assertEqual(refreshed["execution_id"], "refresh")
            self.assertEqual(read.call_count, 4)

    def test_read_only_privileges_fail_closed_and_root_cannot_execute(self):
        connection = MagicMock()
        for grants, allowed in [
            (["GRANT USAGE ON *.* TO 'reader'@'localhost'", "GRANT SELECT ON db.* TO 'reader'@'localhost'"], True),
            (["GRANT SELECT, SHOW VIEW ON db.* TO 'reader'@'localhost'"], True),
            (["GRANT SELECT, INSERT ON db.* TO 'reader'@'localhost'"], False),
            (["GRANT ALL PRIVILEGES ON db.* TO 'reader'@'localhost'"], False),
            (["GRANT SELECT ON db.* TO 'reader'@'localhost' WITH GRANT OPTION"], False),
            (["GRANT `report_role`@`%` TO `reader`@`localhost`"], False),
        ]:
            connection.execute.return_value = [(grant,) for grant in grants]
            self.assertEqual(db.verified_read_only_account(connection), allowed)
        with patch.object(db, "read_connection", return_value=nullcontext(connection)):
            with self.assertRaisesRegex(db.DatabaseError, "SELECT-only"):
                db.run_report.__wrapped__(DatabaseSettings("root", "secret"), "diagnostic", "SELECT 1", {})
        connection.execution_options.assert_not_called()

    def test_busy_report_does_not_start_a_second_database_query(self):
        lock = threading.Lock()
        lock.acquire()
        try:
            with patch.object(db, "report_lock", return_value=lock), patch.object(db, "read_connection") as read:
                with self.assertRaisesRegex(db.DatabaseError, "Another warehouse report"):
                    db.run_report.__wrapped__(DatabaseSettings("reader", "secret"), "diagnostic", "SELECT 1", {})
                read.assert_not_called()
        finally:
            lock.release()

    def test_query_errors_are_sanitized_and_release_the_execution_lock(self):
        from sqlalchemy.exc import OperationalError
        connection = self.connection()
        lock = threading.Lock()
        connection.execution_options.return_value.execute.side_effect = OperationalError(
            "private-sql", {}, Exception(2013, "private-password must never appear"))
        engine = MagicMock()
        engine.connect.return_value.__enter__.return_value = connection
        with patch.object(db, "get_engine", return_value=engine), patch.object(db, "report_lock", return_value=lock), patch.object(db, "verified_read_only_account", return_value=True):
            with self.assertRaises(db.DatabaseError) as caught:
                db.run_report.__wrapped__(DatabaseSettings("reader", "secret"), "diagnostic", "SELECT 1", {})
        self.assertNotIn("private", str(caught.exception))
        self.assertIn("may still", str(caught.exception))
        self.assertFalse(lock.locked())
        connection.rollback.assert_called_once()

    def test_configurable_timeouts_and_engine_options(self):
        with patch.dict("os.environ", {"DASHBOARD_READ_TIMEOUT_SECONDS": "8000"}, clear=True), patch("dashboard.config.dotenv_values", return_value={}):
            settings = database_settings()
        self.assertEqual(settings.read_timeout, 8000)
        with patch.object(db, "create_engine") as create:
            db.get_engine.__wrapped__(settings)
        self.assertEqual(create.call_args.kwargs["connect_args"]["read_timeout"], 8000)
        self.assertFalse(create.call_args.kwargs["connect_args"]["local_infile"])
        with patch.dict("os.environ", {"DASHBOARD_READ_TIMEOUT_SECONDS": "0"}, clear=True), patch("dashboard.config.dotenv_values", return_value={}):
            with self.assertRaises(ValueError):
                database_settings()


class IntegratedAppTests(unittest.TestCase):
    def setUp(self):
        from dashboard_fixtures import saved_fixtures
        self.fixture = saved_fixtures()
        self.fixture.__enter__()
        self.addCleanup(self.fixture.__exit__, None, None, None)

    def test_all_saved_layouts_and_filters_never_query_mysql(self):
        from dashboard_fixtures import start_app, select_report
        with patch.object(db, "warehouse_readiness") as health, patch.object(db, "run_report") as query:
            app = start_app()
            for report in reports.REPORTS:
                select_report(app, report.section, report.id)
                self.assertEqual(len(app.exception), 0)
                borough = next((w for w in app.selectbox if w.label == "Borough"), None)
                if borough:
                    borough.set_value("Manhattan").run()
                    self.assertEqual(len(app.exception), 0)
                    self.assertTrue(app.dataframe[0].value.borough.eq("Manhattan").all())
            health.assert_not_called()
            query.assert_not_called()

    def test_displayed_csv_and_complete_export_preserve_scope_nulls_and_na(self):
        from dashboard_fixtures import start_app, select_report
        with patch("dashboard.sections.common.st.download_button") as download:
            app = select_report(start_app(), "Q3", "q3_location")
            next(w for w in app.selectbox if w.label == "Borough").set_value("Manhattan").run()
            calls = {call.args[0]: call for call in download.call_args_list}
            selected = pd.read_csv(BytesIO(calls["Download CSV"].args[1]), keep_default_na=False, na_values=["\\N"])
            pd.testing.assert_frame_equal(selected, app.dataframe[0].value.reset_index(drop=True), check_dtype=False)
            complete = pd.read_csv(BytesIO(calls["Download complete export"].args[1]), sep="\t", keep_default_na=False, na_values=["\\N"])
            self.assertEqual(len(complete), len(sample_result("q3_location")))
            self.assertGreater(len(complete), len(selected))

    def test_adjust_view_resets_chart_and_population_controls(self):
        from dashboard_fixtures import start_app, select_report
        app = select_report(start_app(), "Q3", "q3_location")
        next(w for w in app.selectbox if w.label == "Borough").set_value("Manhattan").run()
        next(w for w in app.selectbox if w.label == "Location view").set_value("Bubble exploration").run()
        next(w for w in app.checkbox if w.label == "Logarithmic vertical scale").check().run()
        next(b for b in app.button if b.label == "Reset view").click().run()
        self.assertIsNone(next(w for w in app.selectbox if w.label == "Borough").value)
        self.assertEqual(next(w for w in app.selectbox if w.label == "Location view").value, "Hourly profile")
        self.assertEqual(len(app.exception), 0)


if __name__ == "__main__":
    unittest.main()
