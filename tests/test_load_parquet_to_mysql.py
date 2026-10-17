"""Synthetic Parquet checks only: these tests never connect to MySQL."""

import hashlib
import io
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pyarrow as pa
import pyarrow.parquet as pq

import load_parquet_to_mysql as loader


class SerializationTests(unittest.TestCase):
    def test_null_empty_and_literal_null_marker_are_distinct(self):
        self.assertEqual(loader.encode_value(None), r"\N")
        self.assertEqual(loader.encode_value(""), "")
        self.assertEqual(loader.encode_value(r"\N"), r"\\N")

    def test_text_controls_backslashes_quotes_and_unicode(self):
        self.assertEqual(
            loader.encode_value("\\\t\n\r\x00\x1a'\"é"),
            "\\\\\\t\\n\\r\\0\\Z'\"é",
        )

    def test_numbers_keep_precision(self):
        for number in [2**63 - 1, 2**64 - 1, Decimal("12345678901234567890.123400")]:
            self.assertEqual(loader.encode_value(number), str(number))
        for number in [0.1, -0.0, 1.2345678901234567, 5e-324]:
            self.assertEqual(float(loader.encode_value(number)), number)
        self.assertEqual(loader.encode_value(True), "1")
        self.assertEqual(loader.encode_value(False), "0")

    def test_nonfinite_values_are_rejected_instead_of_changed_to_null(self):
        for number in [float("nan"), float("inf"), float("-inf")]:
            with self.assertRaises(ValueError):
                loader.encode_value(number)

    def test_batch_file_retains_nulls_precision_and_windows_safe_newlines(self):
        batch = pa.record_batch([
            pa.array([2**63 - 1, None], type=pa.int64()),
            pa.array([Decimal("1234567890.123400"), None], type=pa.decimal128(20, 6)),
            pa.array([datetime(2025, 1, 1, 0, 0, 0, 123456), None], type=pa.timestamp("us")),
            pa.array([r"\N", "\t\n"]),
        ], names=["id", "amount", "time", "text"])
        with TemporaryDirectory() as directory:
            path = Path(directory) / "batch.tsv"
            loader.write_batch(batch, path, {"time": ("datetime", None, None, 6),
                                           "id": ("bigint", 19, 0, None)})
            self.assertEqual(path.read_bytes(), (
                "9223372036854775807\t1234567890.123400\t2025-01-01 00:00:00.123456\t\\\\N\n"
                "\\N\t\\N\t\\N\t\\t\\n\n"
            ).encode("utf-8"))

    def test_timestamp_precision_loss_is_rejected(self):
        cases = [
            (pa.array([1], type=pa.timestamp("ns")), 6),
            (pa.array([123456], type=pa.timestamp("us")), 3),
            (pa.array([1], type=pa.timestamp("us")), 0),
        ]
        with TemporaryDirectory() as directory:
            for array, fsp in cases:
                with self.subTest(type=array.type, fsp=fsp):
                    with self.assertRaises((ValueError, pa.ArrowInvalid)):
                        loader.write_batch(pa.record_batch([array], names=["time"]),
                                           Path(directory) / "batch.tsv",
                                           {"time": ("datetime", None, None, fsp)})

    def test_whole_second_timestamps_fit_legacy_datetime(self):
        batch = pa.record_batch([pa.array([1000000000], type=pa.timestamp("ns"))], names=["time"])
        with TemporaryDirectory() as directory:
            loader.write_batch(batch, Path(directory) / "batch.tsv",
                               {"time": ("datetime", None, None, 0)})

    def test_unsupported_types_fail_explicitly(self):
        for arrow_type in [pa.timestamp("us", tz="UTC"), pa.list_(pa.int64()), pa.decimal256(70, 2)]:
            with self.assertRaises(ValueError):
                loader.mysql_type(arrow_type)

    def test_schema_validation_rejects_lossy_numeric_destinations(self):
        for arrow_type, sql_type, precision, scale in [
            (pa.float64(), "float", 24, None),
            (pa.float64(), "double", 10, 2),
            (pa.decimal128(20, 6), "decimal", 20, 2),
        ]:
            cursor = MagicMock()
            cursor.fetchall.return_value = [("value", sql_type, precision, scale, None)]
            with self.subTest(type=arrow_type, destination=sql_type):
                with self.assertRaises(ValueError):
                    loader.validate_columns(cursor, pa.schema([("value", arrow_type)]))

    def test_legacy_double_integer_column_must_preserve_each_integer(self):
        columns = {"id": ("double", 53, None, None)}
        with TemporaryDirectory() as directory:
            path = Path(directory) / "batch.tsv"
            exact = pa.record_batch([pa.array([1, None, 2**54], type=pa.int64())], names=["id"])
            loader.write_batch(exact, path, columns)
            inexact = pa.record_batch([pa.array([2**53 + 1], type=pa.int64())], names=["id"])
            with self.assertRaisesRegex(ValueError, "integer precision"):
                loader.write_batch(inexact, path, columns)


class LoadDataTests(unittest.TestCase):
    def test_uses_explicit_columns_and_windows_compatible_path(self):
        cursor = MagicMock(rowcount=2)
        cursor.fetchone.return_value = (0,)
        loader.load_batch(cursor, Path("batch.tsv"), ["id", "a`b"], 2)
        sql, args = cursor.execute.call_args_list[0].args
        self.assertIn("LOAD DATA LOCAL INFILE %s", sql)
        self.assertIn("(`id`, `a``b`)", sql)
        self.assertIn(r"ESCAPED BY '\\'", sql)
        self.assertNotIn("\\", args[0])

    def test_warning_or_skipped_rows_fail_the_load(self):
        cursor = MagicMock(rowcount=1)
        cursor.fetchone.return_value = (1,)
        cursor.fetchall.return_value = [("Warning", 1265, "Data truncated")]
        with self.assertRaisesRegex(RuntimeError, "warning"):
            loader.load_batch(cursor, Path("batch.tsv"), ["id"], 1)
        cursor.fetchone.return_value = (0,)
        with self.assertRaisesRegex(RuntimeError, "Expected 2"):
            loader.load_batch(cursor, Path("batch.tsv"), ["id"], 2)

    def test_legacy_nonempty_destination_is_not_appended_to(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [("InnoDB",), ("InnoDB",), None, (1,)]
        with self.assertRaisesRegex(RuntimeError, "without import history"):
            loader.prepare_tables(cursor, pa.schema([("id", pa.int64())]))
        statements = [call.args[0].upper() for call in cursor.execute.call_args_list]
        self.assertFalse(any(sql.startswith(("DROP", "DELETE", "TRUNCATE", "ALTER"))
                             for sql in statements))

    def test_nontransactional_table_is_rejected(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = ("MyISAM",)
        with self.assertRaisesRegex(RuntimeError, "InnoDB"):
            loader.require_innodb(cursor, loader.DB_TABLE)


class MonthlyImportTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "yellow_tripdata_2025-01.parquet"
        self.batch_path = Path(self.directory.name) / "batch.tsv"
        pq.write_table(pa.table({"id": [1, 2, None, 4, 5]}), self.path, row_group_size=3)
        self.connection = MagicMock()
        self.cursor = MagicMock()
        self.cursor.fetchall.side_effect = [[], [("id", "bigint", 19, 0, None)]]
        self.addCleanup(patch.stopall)
        patch("load_parquet_to_mysql.CHUNKSIZE", 2).start()
        self.stdout = redirect_stdout(io.StringIO())
        self.stdout.__enter__()
        self.addCleanup(self.stdout.__exit__, None, None, None)
        self.progress = patch("load_parquet_to_mysql.tqdm").start()

    def test_batches_commit_once_with_history_after_last_load(self):
        events = []
        with patch.object(loader, "load_batch", side_effect=lambda *args: events.append(args[-1])):
            self.connection.commit.side_effect = lambda: events.append("commit")
            self.assertEqual(loader.import_file(self.connection, self.cursor, self.path, self.batch_path), 5)
        self.assertEqual(events, [2, 2, 1, "commit"])
        self.connection.rollback.assert_not_called()
        sql, args = self.cursor.execute.call_args.args
        self.assertTrue(sql.startswith("INSERT INTO `_parquet_imports`"))
        self.assertEqual(args[1:], (self.path.name, loader.file_digest(self.path), 5))

    def test_late_batch_failure_rolls_back_and_never_marks_complete(self):
        with patch.object(loader, "load_batch", side_effect=[None, RuntimeError("load failed")]):
            with self.assertRaisesRegex(RuntimeError, "load failed"):
                loader.import_file(self.connection, self.cursor, self.path, self.batch_path)
        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_called_once()
        self.assertFalse(any(call.args[0].startswith("INSERT INTO")
                             for call in self.cursor.execute.call_args_list))

    def test_completion_record_failure_also_rolls_back_data(self):
        def execute(sql, *args):
            if sql.startswith("INSERT INTO"):
                raise RuntimeError("history failed")
        self.cursor.execute.side_effect = execute
        with patch.object(loader, "load_batch"):
            with self.assertRaisesRegex(RuntimeError, "history failed"):
                loader.import_file(self.connection, self.cursor, self.path, self.batch_path)
        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_called_once()

    def test_interrupt_rolls_back_current_month(self):
        with patch.object(loader, "load_batch", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                loader.import_file(self.connection, self.cursor, self.path, self.batch_path)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    def test_completed_file_or_renamed_identical_file_is_skipped(self):
        self.cursor.fetchall.side_effect = None
        self.cursor.fetchall.return_value = [("old-name.parquet", loader.file_digest(self.path), 5)]
        with patch.object(loader, "load_batch") as load:
            self.assertEqual(loader.import_file(self.connection, self.cursor, self.path, self.batch_path), 0)
        load.assert_not_called()
        self.connection.commit.assert_not_called()

    def test_changed_completed_filename_is_rejected(self):
        self.cursor.fetchall.side_effect = None
        self.cursor.fetchall.return_value = [(self.path.name, "0" * 64, 5)]
        with self.assertRaisesRegex(RuntimeError, "changed since"):
            loader.import_file(self.connection, self.cursor, self.path, self.batch_path)
        self.connection.commit.assert_not_called()

    def test_checksum_is_sha256_of_original_bytes(self):
        self.assertEqual(loader.file_digest(self.path), hashlib.sha256(self.path.read_bytes()).hexdigest())


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.addCleanup(patch.stopall)
        patch.object(loader, "PARQUET_DIR", self.root).start()
        self.get_engine = patch.object(loader, "get_db_engine").start()
        self.connection = self.get_engine.return_value.raw_connection.return_value
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.cursor.fetchone.side_effect = [(1,), ("NO_BACKSLASH_ESCAPES",), (1,)]
        self.prepare = patch.object(loader, "prepare_tables").start()
        self.load = patch.object(loader, "import_file", return_value=1).start()
        stdout = redirect_stdout(io.StringIO())
        stdout.__enter__()
        self.addCleanup(stdout.__exit__, None, None, None)
        for month in [3, 1, 2]:
            pq.write_table(pa.table({"id": [month]}), self.root / f"2025-{month:02}.parquet")

    def test_files_are_sequential_and_temporary_file_is_cleaned_up(self):
        loader.load_parquet_files_to_mysql()
        self.assertEqual([call.args[2].name for call in self.load.call_args_list],
                         ["2025-01.parquet", "2025-02.parquet", "2025-03.parquet"])
        self.assertFalse(self.load.call_args.args[3].parent.exists())
        self.connection.close.assert_called_once()
        self.get_engine.return_value.dispose.assert_called_once()

    def test_single_file_option_does_not_import_other_months(self):
        loader.load_parquet_files_to_mysql("2025-02.parquet")
        self.load.assert_called_once()
        self.assertEqual(self.load.call_args.args[2].name, "2025-02.parquet")

    def test_disabled_local_loading_or_busy_target_stops_before_setup(self):
        for answers in [[(0,)], [(1,), ("",), (0,)]]:
            self.cursor.fetchone.side_effect = answers
            with self.assertRaises(RuntimeError):
                loader.load_parquet_files_to_mysql()
        self.prepare.assert_not_called()
        self.load.assert_not_called()

    def test_missing_file_and_invalid_chunk_size_do_not_connect(self):
        with self.assertRaises(FileNotFoundError):
            loader.load_parquet_files_to_mysql("missing.parquet")
        with patch.object(loader, "CHUNKSIZE", 0):
            with self.assertRaises(ValueError):
                loader.load_parquet_files_to_mysql()
        self.get_engine.assert_not_called()


if __name__ == "__main__":
    unittest.main()
