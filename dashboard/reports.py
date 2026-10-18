"""Result contracts taken from olap_queries.sql; no analytical SQL is authored here."""

import json
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from dashboard.config import WAREHOUSE_TABLES

HERE = Path(__file__).resolve().parent
FILTER_NAMES = {
    "borough", "zone", "month", "start_date", "end_date", "time_period",
    "fare_min", "fare_max", "distance_category", "aggregation",
}


@dataclass(frozen=True)
class Report:
    id: str
    section: str
    title: str
    columns: tuple
    numeric: tuple
    note: str
    geography: bool = False
    time_labels: tuple = ()


REPORTS = (
    Report("q1_demand", "Q1", "Zone and borough demand",
           ("borough", "zone", "weekday_late_night_pickups", "weekend_late_night_pickups",
            "all_weekend_pickups", "total_filtered_pickups"),
           ("weekday_late_night_pickups", "weekend_late_night_pickups", "all_weekend_pickups", "total_filtered_pickups"),
           "Weekend late-night pickups are included in all-weekend pickups; these series overlap.",
           True, ("Late Night",)),
    Report("q1_hourly", "Q1", "Hourly demand trends",
           ("borough", "time_period", "hour", "weekday_pickups", "weekend_pickups",
            "avg_weekday_hourly_pickups", "avg_weekend_hourly_pickups"),
           ("hour", "weekday_pickups", "weekend_pickups", "avg_weekday_hourly_pickups", "avg_weekend_hourly_pickups"),
           "The existing hourly averages use dates represented in each group, which may exclude zero-trip dates.", True),
    Report("q1_monthly", "Q1", "Monthly late-night consistency",
           ("zone", "yr", "qtr", "mo", "late_night_pickups"), ("late_night_pickups",),
           "Chart totals use month-level zone rows; date and zone rollups remain in the result table.",
           True, ("Late Night",)),
    Report("q2_fare", "Q2", "Payment methods across fare ranges",
           ("fare_range", "credit_card_trips", "cash_trips", "other_payment_trips", "total_trips", "avg_tip_amount"),
           ("credit_card_trips", "cash_trips", "other_payment_trips", "total_trips", "avg_tip_amount"),
           "The existing report includes positive fares. TLC records credit-card tips; cash tips are not captured."),
    Report("q2_payment", "Q2", "Payment distribution by borough and time",
           ("borough", "time_period", "payment_method", "trip_count", "avg_fare", "avg_tip", "avg_total"),
           ("trip_count", "avg_fare", "avg_tip", "avg_total"),
           "The existing report includes positive fares. Subtotal rows are excluded from charts.", True),
    Report("q3_comparison", "Q3", "Rush-hour versus off-peak travel",
           ("borough", "distance_bucket", "rush_hour_duration_min", "off_peak_duration_min",
            "rush_hour_speed_mph", "off_peak_speed_mph"),
           ("rush_hour_duration_min", "off_peak_duration_min", "rush_hour_speed_mph", "off_peak_speed_mph"),
           "The existing comparison uses weekdays, positive distance, and positive duration. Group averages are not averaged together.",
           True, ("Morning Rush", "Evening Rush", "Rush Hour")),
    Report("q3_location", "Q3", "Travel efficiency by location",
           ("borough", "zone", "time_period", "hour", "trip_count", "avg_distance_miles", "avg_duration_minutes", "avg_speed_mph"),
           ("hour", "trip_count", "avg_distance_miles", "avg_duration_minutes", "avg_speed_mph"),
           "The existing location report covers weekday trips of 2–5 miles with positive duration. Other distance scopes need validated SQL.", True),
)


def report_config(report_id):
    try:
        registry = json.loads((HERE / "reports.json").read_text(encoding="utf-8"))
        config = registry[report_id]
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError("The dashboard report registry is missing or invalid") from None
    if not isinstance(config, dict):
        raise ValueError("Each report registry entry must be an object")
    return config


def approved_sql(report, config):
    if config.get("validated") is not True or config.get("aggregated") is not True:
        raise ValueError("This report is waiting for validated, aggregated student-authored SQL")
    if any(not isinstance(config.get(key), str) or not config[key].strip() for key in ("population", "grain")):
        raise ValueError("Record the approved population and result grain before enabling a report")
    query_root = (HERE / "queries").resolve()
    filename = config.get("sql_file", "")
    if not isinstance(filename, str):
        raise ValueError("Report SQL filename must be a string")
    if filename == "olap_queries_optimized.sql":
        # Select a verbatim statement from the team's single authoritative file.
        # No copying, predicate injection, wrapping, or query rewriting.
        try:
            payload = (HERE.parent / filename).read_bytes()
            if source_fingerprint(payload) != config.get("source_sha256"):
                raise ValueError("The approved SQL file changed. Ask the team to review its registry fingerprint before running it")
            statements = split_statements(payload.decode("utf-8-sig"))
            number = config.get("statement")
            if type(number) is not int or len(statements) != 7 or not 1 <= number <= 7:
                raise ValueError("The optimized SQL registry must select one of seven statements")
            sql = statements[number - 1]
        except (OSError, UnicodeError):
            raise ValueError("The approved optimized SQL file is unavailable") from None
    else:
        path = (query_root / filename).resolve()
        if path.parent != query_root or path.suffix.lower() != ".sql":
            raise ValueError("Report SQL must be a .sql file directly inside dashboard/queries")
        try:
            sql = path.read_text(encoding="utf-8-sig")
        except OSError:
            raise ValueError("The approved SQL file has not been added to dashboard/queries") from None
    validate_read_only_sql(sql)
    filters = config.get("filters", {})
    if not isinstance(filters, dict) or set(filters) - FILTER_NAMES:
        raise ValueError("The report declares unsupported filters")
    if any(not isinstance(value, str) or not re.fullmatch(r"[A-Za-z_]\w*", value) for value in filters.values()):
        raise ValueError("Filter bindings must be SQL parameter names")
    if len(set(filters.values())) != len(filters):
        raise ValueError("Each filter needs its own SQL parameter")
    for pair in (("start_date", "end_date"), ("fare_min", "fare_max")):
        if len(set(pair) & set(filters)) == 1:
            raise ValueError(f"Declare both {pair[0]} and {pair[1]}")
    if set(text(sql).compile().params) != set(filters.values()):
        raise ValueError("SQL bind parameters must exactly match the approved filter bindings")
    return sql


def source_fingerprint(payload):
    # Git may check out LF or CRLF. Normalize line endings only for approval
    # comparison; execution still receives the original selected text.
    return hashlib.sha256(payload.decode("utf-8-sig").replace("\r\n", "\n").encode("utf-8")).hexdigest()


def split_statements(source):
    """Split trusted SQL at delimiters outside quotes/comments, retaining SQL text."""
    tokens = r"'(?:''|\\.|[^'\\])*'|\"(?:\"\"|\\.|[^\"\\])*\"|`(?:``|[^`])*`|--[^\n]*|\#[^\n]*|/\*.*?\*/|;"
    statements, start = [], 0
    for match in re.finditer(tokens, source, re.S):
        if match.group() == ";":
            statements.append(source[start:match.end()].strip())
            start = match.end()
    trailing = source[start:].strip()
    if re.sub(r"/\*.*?\*/|--[^\n]*|\#[^\n]*", "", trailing, flags=re.S).strip():
        statements.append(trailing)
    return statements


def validate_read_only_sql(sql):
    """Conservative guard for trusted local SQL, backed by a read-only transaction.

    This is not a general SQL sandbox. A SELECT-only MySQL account is recommended.
    Quotes/comments are removed for inspection; the original SQL is executed unchanged.
    """
    if "/*!" in sql:
        raise ValueError("Executable MySQL comments are not supported")
    tokens = re.sub(r"'(?:''|\\.|[^'\\])*'|\"(?:\"\"|\\.|[^\"\\])*\"|`(?:``|[^`])*`", " quoted ", sql)
    tokens = re.sub(r"/\*.*?\*/|--[^\n]*|\#[^\n]*", " ", tokens, flags=re.S).strip()
    tokens = tokens.rstrip().removesuffix(";").strip()
    if not re.match(r"^(SELECT|WITH)\b", tokens, re.I) or ";" in tokens:
        raise ValueError("A report must contain one read-only SELECT or WITH statement")
    forbidden = r"\b(INSERT|UPDATE|DELETE|REPLACE|CREATE|ALTER|DROP|TRUNCATE|CALL|SET|LOAD|GRANT|REVOKE|INTO|OUTFILE|DUMPFILE|LOCK|UNLOCK|SLEEP|BENCHMARK|GET_LOCK|RELEASE_LOCK)\b|@"
    if re.search(forbidden, tokens, re.I):
        raise ValueError("Only read-only reporting statements are allowed")
    # Inspect table names separately so backtick-quoted warehouse names still work.
    names_sql = re.sub(r"'(?:''|\\.|[^'\\])*'|\"(?:\"\"|\\.|[^\"\\])*\"", "''", sql)
    names_sql = re.sub(r"/\*.*?\*/|--[^\n]*|\#[^\n]*", " ", names_sql, flags=re.S).replace("`", "")
    # Require explicit JOINs so a second comma-separated table cannot bypass
    # the FROM/JOIN allowlist. Track nesting to allow commas in functions/CTEs.
    depth, from_depths = 0, set()
    for token in re.findall(r"[A-Za-z_]\w*|[(),]", names_sql):
        if token == "(":
            depth += 1
        elif token == ")":
            from_depths.discard(depth)
            depth -= 1
        elif token.upper() == "FROM":
            from_depths.add(depth)
        elif token.upper() in {"WHERE", "GROUP", "HAVING", "ORDER", "LIMIT", "UNION"}:
            from_depths.discard(depth)
        elif token == "," and depth in from_depths:
            raise ValueError("Use explicit JOINs rather than comma-separated report tables")
    ctes = set(re.findall(r"(?:\bWITH\s+(?:RECURSIVE\s+)?|,)\s*(\w+)\s+AS\s*\(", names_sql, re.I))
    for name in re.findall(r"\b(?:FROM|JOIN)\s+([\w.]+)", names_sql, re.I):
        if "." in name or name not in set(WAREHOUSE_TABLES) | ctes:
            raise ValueError("Use unqualified warehouse tables or local CTEs; raw/source tables are not report inputs")


def validate_result(report, data):
    missing = set(report.columns) - set(data.columns)
    if missing:
        raise ValueError("Report result is missing columns: " + ", ".join(sorted(missing)))
    result = data.copy()
    for column in report.numeric:
        try:
            result[column] = pd.to_numeric(result[column], errors="raise")
        except (ValueError, TypeError):
            raise ValueError(f"Report column {column} must contain numbers or NULLs") from None
    return result


def live_blockers(report, readiness):
    problems = []
    if not readiness.get("connected"):
        return ["MySQL connection is unavailable"]
    if readiness.get("read_only_account") is False:
        problems.append("Configure a dedicated SELECT-only dashboard login before running live reports. The current account is not verified as read-only")
    if (readiness.get("error") or set(readiness["tables"]) != set(WAREHOUSE_TABLES)
            or any(value != "Has records" for value in readiness["tables"].values())):
        problems.append("All six warehouse tables must exist and contain records")
    if report.time_labels and not set(report.time_labels) & set(readiness.get("time_periods", [])):
        problems.append("Required time classifications are absent from dim_time")
    if report.geography and readiness.get("placeholder_locations"):
        problems.append("dim_location still contains generated Zone <ID> placeholders")
    return problems
