"""Schema contracts plus opt-in, read-only MySQL grammar/fixture checks.

NYC_ETL_READONLY_TESTS=1 enables only PREPARE (never EXECUTE) and SELECTs over
synthetic CTE rows. No schema, view, routine, source or fact data is created.
"""

import csv
import io
import os
import re
import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL = (ROOT / "load_star_schema.sql").read_text(encoding="utf-8")
VIEW_SELECT = re.search(r"VIEW etl_trip_source_2025 AS\n(SELECT.*?);", SQL, re.S).group(1)

FACT_COLUMNS = {
    "trip_id": "BIGINT", "pu_date_id": "INT", "do_date_id": "INT",
    "pu_time_id": "INT", "do_time_id": "INT", "pu_location_id": "INT",
    "do_location_id": "INT", "payment_id": "INT", "rate_code_id": "INT",
    "trip_distance": "DECIMAL(8,2)", "trip_duration_seconds": "INT",
    "estimated_speed_mph": "DECIMAL(6,2)",
    **{name: "DECIMAL(10,2)" for name in (
        "fare_amount", "extra", "mta_tax", "tip_amount", "tolls_amount",
        "improvement_surcharge", "total_amount", "airport_fee", "cbd_congestion_fee",
    )},
}


class WarehouseContractTests(unittest.TestCase):
    def test_fact_types_and_all_eight_relationships_match_diagram(self):
        schema = (ROOT / "schema.sql").read_text()
        fact = re.search(r"CREATE TABLE fact_trip_records \((.*?)\) ENGINE", schema, re.S).group(1)
        columns = dict(re.findall(r"^\s*(\w+)\s+(BIGINT|INT|DECIMAL\(\d+,\s*\d+\))", fact, re.M))
        self.assertEqual({key: value.replace(" ", "") for key, value in columns.items()}, FACT_COLUMNS)
        relationships = dict(re.findall(r"FOREIGN KEY \((\w+)\) REFERENCES (\w+) \(\w+\)", fact))
        self.assertEqual(relationships, {
            "pu_date_id": "dim_date", "do_date_id": "dim_date",
            "pu_time_id": "dim_time", "do_time_id": "dim_time",
            "pu_location_id": "dim_location", "do_location_id": "dim_location",
            "payment_id": "dim_payment", "rate_code_id": "dim_rate_code",
        })

    def test_all_dimension_columns_match_diagram(self):
        expected = {
            "dim_date": {"date_id": "INT", "date": "DATE", "is_weekend": "BOOLEAN", "day_of_week": "VARCHAR(10)", "month": "SMALLINT", "quarter": "SMALLINT", "year": "SMALLINT"},
            "dim_time": {"time_id": "INT", "minute": "SMALLINT", "hour": "SMALLINT", "time_period": "VARCHAR(20)"},
            "dim_location": {"location_id": "INT", "zone": "VARCHAR(100)", "borough": "VARCHAR(50)"},
            "dim_payment": {"payment_id": "INT", "payment_method": "VARCHAR(30)"},
            "dim_rate_code": {"rate_code_id": "INT", "rate_description": "VARCHAR(50)"},
        }
        schema = (ROOT / "schema.sql").read_text()
        for table, columns in expected.items():
            body = re.search(r"CREATE TABLE " + table + r" \((.*?)\) ENGINE", schema, re.S).group(1)
            found = dict(re.findall(r"^\s*`?(\w+)`?\s+(INT|DATE|BOOLEAN|SMALLINT|VARCHAR\(\d+\))", body, re.M))
            self.assertEqual(found, columns, table)
            self.assertIn("PRIMARY KEY (" + next(iter(columns)) + ")", body)

    def test_one_loader_and_no_automatic_installation_load(self):
        self.assertEqual(len(re.findall(r"INSERT INTO fact_trip_records\s*\(", SQL)), 1)
        columns = re.search(r"INSERT INTO fact_trip_records \((.*?)\)\s*SELECT", SQL, re.S).group(1)
        self.assertEqual({part.strip() for part in columns.split(",")}, set(FACT_COLUMNS) - {"trip_id"})
        self.assertNotRegex(SQL, r"(?m)^CALL ")
        self.assertNotIn("OFFSET", SQL)
        self.assertNotRegex(SQL, r"(?i)SET\s+(?:SESSION\s+)?(?:FOREIGN_KEY_CHECKS|UNIQUE_CHECKS|SQL_LOG_BIN)\s*=\s*0")
        self.assertIn("CALL SeedTaxiDimensions2025()", (ROOT / "seed_dimensions.sql").read_text())
        self.assertIn("CALL LoadTaxiFacts2025()", (ROOT / "load_fact.sql").read_text())
        for filename in ("load_fact_batched.sql", "load_star_scehma_recurssive.sql"):
            content = (ROOT / filename).read_text()
            self.assertIn("SIGNAL SQLSTATE '45000'", content)
            self.assertNotIn("INSERT INTO", content)

    def test_zone_seed_matches_pinned_official_lookup(self):
        rows = csv.DictReader(io.StringIO((ROOT / "reference_data/taxi_zone_lookup.csv").read_text(encoding="utf-8-sig")))
        official = {int(row["LocationID"]): (row["Zone"], row["Borough"]) for row in rows}
        self.assertEqual(set(official), set(range(1, 266)))
        found = {int(key): (zone.replace("''", "'"), borough.replace("''", "'")) for key, zone, borough in re.findall(r"^\((\d+), '((?:''|[^'])*)', '((?:''|[^'])*)'\)", SQL, re.M)}
        self.assertEqual({key: value for key, value in found.items() if key != 0}, official)
        self.assertEqual(found[0], ("Unknown Zone", "Unknown Borough"))


@unittest.skipUnless(os.environ.get("NYC_ETL_READONLY_TESTS") == "1", "Opt-in read-only MySQL checks")
class ReadOnlyMySQLTests(unittest.TestCase):
    def setUp(self):
        from dashboard.config import database_settings
        from dashboard.db import read_connection
        self.context = read_connection(database_settings())
        self.connection = self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)

    def test_mysql_parses_procedures_without_creating_them(self):
        from sqlalchemy.exc import SQLAlchemyError
        procedures = re.findall(r"CREATE PROCEDURE .*?\nEND\$\$", SQL, re.S)
        self.assertEqual(len(procedures), 2)
        for statement in procedures:
            self.connection.exec_driver_sql("SET @nyc_etl_parser_test = %s", (statement[:-2],))
            try:
                self.connection.exec_driver_sql("PREPARE nyc_etl_parser_test FROM @nyc_etl_parser_test")
            except SQLAlchemyError as error:
                # MySQL parses the complete routine, then refuses PREPARE for
                # this statement type. Invalid grammar instead returns 1064.
                self.assertEqual(error.orig.args[0], 1295, str(error.orig))
            else:
                self.connection.exec_driver_sql("DEALLOCATE PREPARE nyc_etl_parser_test")
        self.connection.exec_driver_sql("SET @nyc_etl_parser_test = NULL")

    def test_seed_generators_cover_every_minute_and_calendar_boundary(self):
        from sqlalchemy import text
        old = self.connection.exec_driver_sql("SELECT @@SESSION.cte_max_recursion_depth").scalar()
        try:
            self.connection.exec_driver_sql("SET SESSION cte_max_recursion_depth = 2000")
            time_query = re.search(r"INSERT INTO dim_time .*?\n    (WITH RECURSIVE.*?FROM minutes)\n    ON DUPLICATE", SQL, re.S).group(1)
            times = self.connection.execute(text(time_query)).all()
            self.assertEqual(len(times), 1440)
            for key, minute, hour, period in times:
                self.assertEqual(key, hour * 60 + minute)
                expected = "Late Night" if hour < 6 or hour >= 20 else "Morning Rush" if hour < 10 else "Midday" if hour < 16 else "Evening Rush"
                self.assertEqual(period, expected)
            date_query = re.search(r"INSERT INTO dim_date .*?\n    (WITH RECURSIVE.*?FROM calendar)\n    ON DUPLICATE", SQL, re.S).group(1)
            dates = self.connection.execute(text(date_query)).all()
            self.assertEqual(len(dates), 366)
            for key, day, weekend, day_name, month, quarter, year in dates:
                self.assertEqual((key, weekend, day_name, month, quarter, year),
                                 (int(day.strftime("%Y%m%d")), int(day.weekday() >= 5), day.strftime("%A"), day.month, (day.month - 1) // 3 + 1, day.year))
            self.assertEqual(dates[-1][1], date(2026, 1, 1))
        finally:
            self.connection.exec_driver_sql("SET SESSION cte_max_recursion_depth = %s", (old,))

    def run_fixture(self, **changes):
        from sqlalchemy import text
        fixture = {
            "tpep_pickup_datetime": datetime(2025, 1, 1),
            "tpep_dropoff_datetime": datetime(2025, 1, 1, 0, 10),
            "PULocationID": 161, "DOLocationID": 265, "payment_type": 1, "RatecodeID": 1,
            "trip_distance": 2.0, "fare_amount": 10.0, "extra": None, "mta_tax": None,
            "tip_amount": None, "tolls_amount": None, "improvement_surcharge": None,
            "total_amount": 10.0, "Airport_fee": None, "cbd_congestion_fee": None,
        }
        fixture.update(changes)
        fields = []
        for name in fixture:
            sql_type = "DATETIME(6)" if name.startswith("tpep_") else "SIGNED" if name in {"PULocationID", "DOLocationID", "payment_type", "RatecodeID"} else "DOUBLE"
            fields.append(f"CAST(:{name} AS {sql_type}) AS {name}")
        # The CTE shadows the real raw table. This never scans actual trips.
        query = "WITH yellow_taxi_trips AS (SELECT " + ", ".join(fields) + ") " + VIEW_SELECT
        return self.connection.execute(text(query), fixture).mappings().all()

    def test_date_eligibility_and_year_boundary(self):
        start = datetime(2025, 1, 1)
        cases = [
            ({}, True),
            ({"tpep_pickup_datetime": datetime(2024, 12, 31)}, False),
            ({"tpep_pickup_datetime": datetime(2026, 1, 1), "tpep_dropoff_datetime": datetime(2026, 1, 1, 1)}, False),
            ({"tpep_pickup_datetime": None}, False),
            ({"tpep_dropoff_datetime": None}, False),
            ({"tpep_dropoff_datetime": start}, False),
            ({"tpep_dropoff_datetime": start - timedelta(seconds=1)}, False),
            ({"tpep_dropoff_datetime": start + timedelta(hours=24)}, True),
            ({"tpep_dropoff_datetime": start + timedelta(hours=24, microseconds=1)}, False),
            ({"tpep_dropoff_datetime": start + timedelta(microseconds=999999)}, False),
        ]
        for changes, accepted in cases:
            with self.subTest(changes=changes):
                self.assertEqual(bool(self.run_fixture(**changes)), accepted)
        rows = self.run_fixture(tpep_pickup_datetime=datetime(2025, 12, 31, 23, 59), tpep_dropoff_datetime=datetime(2026, 1, 1, 0, 1))
        self.assertEqual(rows[0]["do_date_id"], 20260101)

    def test_nulls_refunds_codes_distance_and_speed(self):
        row = self.run_fixture(fare_amount=None, trip_distance=None, payment_type=None, RatecodeID=None, PULocationID=None)[0]
        for column in ("fare_amount", "trip_distance", "estimated_speed_mph", "tip_amount"):
            self.assertIsNone(row[column], column)
        self.assertEqual((row["payment_id"], row["rate_code_id"], row["pu_location_id"]), (5, 99, 0))
        row = self.run_fixture(payment_type=0, fare_amount=-10.25, trip_distance=-1.0, PULocationID=999, RatecodeID=999)[0]
        self.assertEqual(row["payment_id"], 0)
        self.assertEqual(row["fare_amount"], Decimal("-10.25"))
        self.assertIsNone(row["trip_distance"])
        self.assertIsNone(row["estimated_speed_mph"])
        self.assertEqual((row["pu_location_id"], row["rate_code_id"]), (0, 99))
        self.assertEqual(self.run_fixture()[0]["estimated_speed_mph"], Decimal("12.00"))
        self.assertEqual(self.run_fixture(trip_distance=0)[0]["estimated_speed_mph"], Decimal("0.00"))
        fast = self.run_fixture(trip_distance=100, tpep_dropoff_datetime=datetime(2025, 1, 1, 0, 0, 1))[0]
        self.assertIsNone(fast["estimated_speed_mph"])

    def test_rounding_and_overflow_diagnostics(self):
        self.assertEqual(self.run_fixture(fare_amount=1.235)[0]["fare_amount"], Decimal("1.24"))
        self.run_fixture(fare_amount=1000000000)
        self.connection.exec_driver_sql("GET DIAGNOSTICS @nyc_test_conditions = NUMBER")
        self.connection.exec_driver_sql("GET DIAGNOSTICS CONDITION 1 @nyc_test_errno = MYSQL_ERRNO")
        count, code = self.connection.exec_driver_sql("SELECT @nyc_test_conditions, @nyc_test_errno").one()
        self.assertGreater(count, 0)
        self.assertEqual(code, 1264)
        self.connection.exec_driver_sql("SET @nyc_test_conditions = NULL, @nyc_test_errno = NULL")


if __name__ == "__main__":
    unittest.main()
