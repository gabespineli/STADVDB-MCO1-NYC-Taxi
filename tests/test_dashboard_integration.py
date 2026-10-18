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
    def app(self):
        app = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=30).run()
        return app.sidebar.radio[1].set_value("Warehouse reports").run()

    def test_all_seven_live_layouts_only_run_on_click_then_filter_without_sql(self):
        def fake_run(settings, report_id, sql, parameters, _request_id=None):
            # Explicitly mocked fixtures validate UI wiring, not real taxi findings.
            return {"data": sample_result(report_id), "fetched_at": "2026-10-19T12:00:00+00:00",
                    "seconds": 1, "execution_id": _request_id}
        with patch.object(db, "warehouse_readiness", return_value=ready_state()), patch.object(db, "run_report", side_effect=fake_run) as run:
            app = self.app()
            run.assert_not_called()
            for section in ("Q1", "Q2", "Q3"):
                app.sidebar.radio[0].set_value(section).run()
                for report in (r for r in reports.REPORTS if r.section == section):
                    app.selectbox[0].set_value(report.id).run()
                    before = run.call_count
                    self.assertFalse(any(widget.label == "Pickup date range" for widget in app.date_input))
                    next(b for b in app.button if b.label == "Load warehouse report").click().run()
                    self.assertEqual(run.call_count, before + 1)
                    self.assertEqual(run.call_args.args[2], reports.approved_sql(report, reports.report_config(report.id)))
                    self.assertEqual(run.call_args.args[3], {})
                    self.assertEqual(len(app.exception), 0)
                    self.assertGreater(len(app.get("plotly_chart")), 0)
                    self.assertFalse(any("SYNTHETIC SAMPLE" in w.value for w in app.warning))
                    self.assertTrue(any("Freshly retrieved" in c.value for c in app.caption))
                    app.run()
                    self.assertEqual(run.call_count, before + 1)
                    borough = next((s for s in app.selectbox if s.label == "Borough"), None)
                    if borough:
                        borough.set_value("Manhattan").run()
                        self.assertEqual(run.call_count, before + 1)
                        self.assertEqual(len(app.exception), 0)
                        visible = app.dataframe[0].value
                        self.assertTrue(visible.borough.eq("Manhattan").all())

    def test_cached_label_refresh_and_unverified_login_block(self):
        report = reports.REPORTS[0]
        result = {"data": sample_result(report.id), "fetched_at": "test UTC", "execution_id": "previous-call", "seconds": 2}
        with patch.object(db, "warehouse_readiness", return_value=ready_state()), patch.object(db, "run_report", return_value=result) as run:
            app = self.app().sidebar.radio[0].set_value("Q1").run()
            next(b for b in app.button if b.label == "Load warehouse report").click().run()
            self.assertTrue(any("Cached database result" in c.value for c in app.caption))
            next(b for b in app.button if b.label == "Refresh from MySQL").click().run()
            run.clear.assert_called_once()
            self.assertEqual(run.call_count, 2)
        state = {**ready_state(), "read_only_account": False}
        with patch.object(db, "warehouse_readiness", return_value=state), patch.object(db, "run_report") as run:
            app = self.app()
            self.assertTrue(any("SELECT-only" in w.value for w in app.warning))
            self.assertTrue(next(b for b in app.button if b.label == "Load warehouse report").disabled)
            self.assertTrue(next(b for b in app.button if b.label == "Refresh from MySQL").disabled)
            run.assert_not_called()

    def test_displayed_csv_and_complete_output_preserve_scope_nulls_and_na(self):
        report = reports.REPORTS[-1]
        data = sample_result(report.id).copy()
        data.loc[0, "avg_speed_mph"] = None
        data.loc[data.index[-1], "borough"] = "N/A"
        result = {"data": data, "fetched_at": "test", "execution_id": "cached", "seconds": 1}
        with patch.object(db, "warehouse_readiness", return_value=ready_state()), patch.object(db, "run_report", return_value=result), patch("dashboard.sections.common.st.download_button") as download:
            app = self.app().sidebar.radio[0].set_value("Q3").run()
            app.selectbox[0].set_value(report.id).run()
            next(b for b in app.button if b.label == "Load warehouse report").click().run()
            next(s for s in app.selectbox if s.label == "Borough").set_value("Manhattan").run()
            calls = {call.args[0]: call for call in download.call_args_list}
            selected = pd.read_csv(BytesIO(calls["Download result CSV"].kwargs["data"]), keep_default_na=False, na_values=["\\N"])
            pd.testing.assert_frame_equal(selected.drop(columns="data_classification"), app.dataframe[0].value.reset_index(drop=True), check_dtype=False)
            complete = pd.read_csv(BytesIO(calls["Download complete SQL output"].args[1]), keep_default_na=False, na_values=["\\N"])
            self.assertIn("N/A", complete.borough.tolist())
            self.assertTrue(complete.avg_speed_mph.isna().any())
            self.assertEqual(len(complete), len(data))


if __name__ == "__main__":
    unittest.main()
