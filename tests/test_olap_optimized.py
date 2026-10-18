"""Bounded equivalence checks. Never benchmark or modify the real warehouse."""

from collections import Counter
import os
from pathlib import Path
import random
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent


def statements(filename):
    sql = (ROOT / filename).read_text(encoding="utf-8")
    return [re.sub(r"--[^\n]*", "", part).strip() for part in sql.split(";")
            if re.sub(r"--[^\n]*", "", part).strip()]


class OptimizationFilesTests(unittest.TestCase):
    def test_seven_read_only_reports_and_index_only_setup(self):
        from dashboard.reports import validate_read_only_sql
        baseline = statements("olap_queries.sql")
        optimized = statements("olap_queries_optimized.sql")
        self.assertEqual(len(baseline), 7)
        self.assertEqual(len(optimized), 7)
        for sql in optimized:
            validate_read_only_sql(sql)
        for index in (0, 6):
            self.assertEqual(optimized[index], baseline[index])
        setup = statements("olap_indexes.sql")
        self.assertEqual(len(setup), 2)
        self.assertTrue(all(sql.startswith("CREATE INDEX idx_olap_") for sql in setup))


@unittest.skipUnless(os.environ.get("NYC_ETL_READONLY_TESTS") == "1", "Opt-in read-only MySQL checks")
class OptimizationMySQLTests(unittest.TestCase):
    def setUp(self):
        import pymysql
        from dashboard.config import database_settings
        settings = database_settings()
        self.connection = pymysql.connect(
            host=settings.host, port=settings.port, user=settings.user,
            password=settings.password, database=settings.database,
            charset="utf8mb4", connect_timeout=5, read_timeout=25,
        )
        self.addCleanup(self.connection.close)
        self.addCleanup(self.connection.rollback)
        with self.connection.cursor() as cursor:
            cursor.execute("START TRANSACTION READ ONLY")
        self.baseline = statements("olap_queries.sql")
        self.optimized = statements("olap_queries_optimized.sql")

    def fixture(self, rows):
        columns = ["trip_id", "pu_location_id", "pu_date_id", "pu_time_id", "payment_id",
                   "trip_distance", "fare_amount", "tip_amount", "total_amount",
                   "trip_duration_seconds", "estimated_speed_mph"]
        types = ["SIGNED"] * 5 + ["DECIMAL(8,2)"] + ["DECIMAL(10,2)"] * 3 + ["SIGNED", "DECIMAL(6,2)"]
        select = "SELECT " + ", ".join(f"CAST(%s AS {kind}) AS {column}" for column, kind in zip(columns, types))
        parameters = [value for row in rows for value in row]
        facts = " UNION ALL ".join([select] * len(rows)) if rows else select + " WHERE FALSE"
        if not rows:
            parameters = [None] * len(columns)
        prefix = "WITH fact_trip_records AS (" + facts + """),
dim_date AS (
 SELECT 1 date_id,CAST('2025-01-01' AS DATE) `date`,0 is_weekend,2025 year,1 quarter,1 month
 UNION ALL SELECT 2,'2025-01-02',0,2025,1,1
 UNION ALL SELECT 3,'2025-01-04',1,2025,1,1
 UNION ALL SELECT 4,'2025-02-03',0,2025,1,2
 UNION ALL SELECT 5,'2025-04-01',0,2025,2,4
 UNION ALL SELECT 6,'2026-01-01',0,2026,1,1
),
dim_time AS (
 SELECT 1 time_id,0 hour,'Late Night' time_period
 UNION ALL SELECT 2,6,'Morning Rush' UNION ALL SELECT 3,6,'Morning Rush'
 UNION ALL SELECT 4,10,'Midday' UNION ALL SELECT 5,16,'Evening Rush'
 UNION ALL SELECT 6,23,'Late Night' UNION ALL SELECT 7,7,'Rush Hour'
 UNION ALL SELECT 8,11,NULL
),
dim_location AS (
 SELECT 1 location_id,'Manhattan' borough,'Alpha' zone
 UNION ALL SELECT 2,'Manhattan','Beta' UNION ALL SELECT 3,'Queens','Shared'
 UNION ALL SELECT 4,'Brooklyn','Shared' UNION ALL SELECT 5,NULL,NULL
 UNION ALL SELECT 6,'Unknown','Outside' UNION ALL SELECT 7,NULL,'Unknown Zone'
),
dim_payment AS (
 SELECT 0 payment_id,'Flex Fare' payment_method
 UNION ALL SELECT 1,'Credit Card' UNION ALL SELECT 2,'Cash'
 UNION ALL SELECT 3,'No Charge' UNION ALL SELECT 4,'Dispute'
 UNION ALL SELECT 5,'Unknown' UNION ALL SELECT 6,'Voided Trip'
)
"""
        return prefix, parameters

    def compare(self, rows):
        prefix, parameters = self.fixture(rows)
        with self.connection.cursor() as cursor:
            for number, (baseline, optimized) in enumerate(zip(self.baseline, self.optimized), 1):
                with self.subTest(report=number, fixture_rows=len(rows)):
                    cursor.execute(prefix + baseline, parameters)
                    expected = cursor.fetchall()
                    columns = tuple(column[0] for column in cursor.description)
                    sql = prefix.rstrip() + ", " + optimized[5:] if optimized.startswith("WITH ") else prefix + optimized
                    cursor.execute(sql, parameters)
                    actual = cursor.fetchall()
                    self.assertEqual(tuple(column[0] for column in cursor.description), columns)
                    # SQL doesn't guarantee the relative order of equal sorting keys.
                    self.assertEqual(Counter(actual), Counter(expected))

    def test_empty_input_and_all_null_measurements(self):
        self.compare([])
        self.compare([(1, 1, 1, 2, 1, 3, 10, None, None, 60, None),
                      (2, 2, 1, 2, 2, 3, 10, None, None, 600, None),
                      (3, 3, 3, 1, 0, None, None, None, None, None, None)])

    def test_weighted_averages_active_dates_boundaries_and_orphans(self):
        rng = random.Random(2025)
        rows = [
            (i, rng.choice([1, 1, 2, 3, 4, 5, 6, 7, 999]), rng.choice([1, 1, 2, 3, 4, 5, 6, 999]),
             rng.choice([1, 2, 3, 4, 5, 6, 7, 8, 999]), rng.choice([0, 1, 2, 3, 4, 5, 6, 999]),
             rng.choice([None, -1, 0, 0.01, 1.99, 2, 4.99, 5, 9.99, 10, 100]),
             rng.choice([None, -10, 0, 0.01, 9.99, 10, 24.99, 25, 49.99, 50, 999.99]),
             rng.choice([None, -1, 0, 1.01, 2.33, 20]), rng.choice([None, -10, 0, 12.34, 80]),
             rng.choice([None, -1, 0, 1, 3, 59, 60, 61, 900, 86400]),
             rng.choice([None, 0, 0.01, 10.25, 100, 9999.99]))
            for i in range(1, 251)
        ]
        self.compare(rows)

    def test_real_warehouse_explain_only(self):
        with self.connection.cursor() as cursor:
            for number, sql in enumerate(self.optimized, 1):
                with self.subTest(report=number):
                    cursor.execute("EXPLAIN " + sql)
                    self.assertTrue(cursor.fetchall())


if __name__ == "__main__":
    unittest.main()
