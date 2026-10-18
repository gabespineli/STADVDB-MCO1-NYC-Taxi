"""Bounded warehouse reads; no raw trip retrieval and no analytical SQL generation."""

from contextlib import contextmanager
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from dashboard.config import MAX_REPORT_ROWS, WAREHOUSE_TABLES
from dashboard.reports import validate_read_only_sql


class DatabaseError(RuntimeError):
    pass


def safe_error(error):
    args = getattr(getattr(error, "orig", None), "args", ())
    code = args[0] if args and isinstance(args[0], int) else None
    return {
        1045: "MySQL rejected the dashboard login. Check the local database credentials.",
        1049: "The configured MySQL database does not exist.",
        1142: "The dashboard account does not have SELECT access to a required table.",
        1146: "A required warehouse table is missing.",
        2003: "MySQL could not be reached. Check the service, host, and port.",
        2013: "The database connection timed out or was interrupted.",
        3024: "The report exceeded the database execution time limit.",
    }.get(code, "The database read failed. Check MySQL availability, SELECT permissions, and the approved SQL locally.")


@st.cache_resource(show_spinner=False, max_entries=3)
def get_engine(settings):
    url = URL.create("mysql+pymysql", username=settings.user, password=settings.password,
                     host=settings.host, port=settings.port, database=settings.database)
    return create_engine(
        url, pool_pre_ping=True, pool_recycle=300, pool_size=2, max_overflow=1,
        hide_parameters=True,
        connect_args={"charset": "utf8mb4", "local_infile": False,
                      "connect_timeout": 5, "read_timeout": 30, "write_timeout": 30},
    )


@contextmanager
def read_connection(settings):
    try:
        with get_engine(settings).connect() as connection:
            connection.exec_driver_sql("START TRANSACTION READ ONLY")
            try:
                yield connection
            finally:
                connection.rollback()
    except SQLAlchemyError as error:
        raise DatabaseError(safe_error(error)) from None


@st.cache_data(ttl=60, show_spinner=False, max_entries=3)
def warehouse_readiness(settings):
    state = {"connected": False, "tables": {}, "time_periods": [], "locations": [],
             "placeholder_locations": False, "checked_at": datetime.now(timezone.utc).isoformat()}
    try:
        with read_connection(settings) as connection:
            connection.execute(text("SELECT 1"))
            state["connected"] = True
            present = set(connection.execute(text(
                "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = :database"
            ), {"database": settings.database}).scalars())
            for table in WAREHOUSE_TABLES:
                if table not in present:
                    state["tables"][table] = "Missing"
                else:
                    # table is from the fixed warehouse allowlist, never user input.
                    exists = connection.execute(text(f"SELECT 1 FROM `{table}` LIMIT 1")).first()
                    state["tables"][table] = "Has records" if exists else "Empty"
            if state["tables"]["dim_time"] == "Has records":
                state["time_periods"] = list(connection.execute(text(
                    "SELECT DISTINCT time_period FROM dim_time LIMIT 32"
                )).scalars())
            if state["tables"]["dim_location"] == "Has records":
                state["locations"] = [dict(row) for row in connection.execute(text(
                    "SELECT location_id, zone, borough FROM dim_location ORDER BY location_id LIMIT 300"
                )).mappings()]
                state["placeholder_locations"] = any(
                    str(row["zone"]).startswith("Zone ") for row in state["locations"] if row["location_id"] != 0
                )
    except DatabaseError as error:
        state["error"] = str(error)
    return state


@st.cache_data(ttl=300, show_spinner=False, max_entries=32)
def run_report(settings, report_id, sql, parameters):
    """Cache the exact SQL + parameters; never append predicates or LIMIT clauses."""
    validate_read_only_sql(sql)
    with read_connection(settings) as connection:
        with connection.execution_options(stream_results=True).execute(text(sql), parameters) as result:
            columns = list(result.keys())
            rows = result.fetchmany(MAX_REPORT_ROWS + 1)
            if len(rows) > MAX_REPORT_ROWS:
                raise ValueError(f"Report exceeds {MAX_REPORT_ROWS:,} aggregated rows. Ask the OLAP author to review the result grain; no partial result is displayed.")
            data = pd.DataFrame(rows, columns=columns)
    return {"data": data, "fetched_at": datetime.now(timezone.utc).isoformat(), "report_id": report_id}
