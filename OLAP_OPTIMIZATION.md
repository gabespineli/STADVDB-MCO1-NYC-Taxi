# Seven OLAP optimization candidates

`olap_queries.sql` remains the unchanged baseline. `olap_queries_optimized.sql`
contains seven reporting statements in the same order and with the same output
columns. The removed `reports/` folder and its Python/CMD runner are not needed.
No candidate is automatically executed or approved in the dashboard.

## Changes by statement

| # | Report | Method |
| --- | --- | --- |
| 1 / Q1a | Weekend/late-night zone and borough demand | Original SELECT, supported by the optional Q1 covering index |
| 2 / Q1b | Hourly weekday/weekend demand | Count per borough/period/hour/date first, then compute active-date averages |
| 3 / Q1c | Monthly late-night consistency | Count by location ID/date ID first, then join zone/calendar descriptions |
| 4 / Q2a | Payment across fare tiers | Aggregate by payment ID/numeric fare tier before the payment-label join |
| 5 / Q2b | Payment by borough and period | Aggregate by location ID/period/payment ID before descriptive joins |
| 6 / Q3a | Rush-hour/off-peak efficiency | Aggregate by location ID/numeric distance tier before borough rollups |
| 7 / Q3b | Weekday 2–5-mile efficiency | Original SELECT, supported by the optional distance-range covering index |

Rewrites retain eligibility filters, category boundaries, NULL handling, and all
rollup levels. Fare and distance rollup labels remain SQL NULL where the baseline
returns NULL. Counts for empty rollups remain zero. Means are reconstructed from
sums and each measurement's own non-NULL count, never by averaging group averages.
Q1b preserves the baseline's active-date denominator and is not changed to a full
calendar-day average. Q1c continues grouping by zone name, as the baseline does.
No new outlier rules, holidays, year restrictions, or dimensional changes are added.

## For your teammate

1. Copy `olap_queries_optimized.sql` and `olap_indexes.sql` into their clone or work
   directory. Use the populated warehouse, not the raw source table. If their
   database has a different name, select it instead of `source_db`.
2. Before long queries or index creation, save work and reclaim any deleted-but-open
   temporary files. Check actual free disk space. The new queries still scan facts
   and may use temporary disk. There is no guaranteed peak disk requirement yet.
3. Open the SQL in MySQL Workbench and execute one complete statement at a time.
   There is no need to run baseline and candidate together or run EXPLAIN ANALYZE.
4. Save each completed result using your team's usual export process. The dashboard
   TSV/metadata format is documented in `dashboard/exports/README.md`.

For the MySQL command-line client, launch it from the directory containing the
files. At the `mysql>` prompt:

```sql
USE source_db;
```

### Optional indexes - run once, before measuring index-based improvements

Inspect existing indexes first:

```sql
SHOW INDEX FROM fact_trip_records;
```

`olap_indexes.sql` adds:

- `idx_olap_q1_cover (pu_time_id, pu_date_id, pu_location_id)`
- `idx_olap_q3_distance_cover (trip_distance, pu_date_id, pu_location_id,
  pu_time_id, trip_duration_seconds, estimated_speed_mph)`

InnoDB secondary indexes also contain the primary key (`trip_id`), covering the
COUNT input in Q1. Indexes are not forced: MySQL selects the access path. Neither
index has been built on the local warehouse by this task. The EXPLAIN checks below
therefore confirm statement compatibility, not adoption of these future indexes.

Building indexes on ~48 million facts can take substantial time and requires free
space for both the final indexes and temporary build work. The Q3 index is wide.
Do not build them on a nearly full drive, during ETL, or concurrently with reports.
If the same names or equivalent column sequences already exist, skip the matching
CREATE statement. Run only the missing statement in Workbench. The setup script
does not auto-detect existing indexes and is not intended for repeated execution.

If both indexes are missing and sufficient space is available:

```sql
SOURCE olap_indexes.sql;
```

Without the new indexes, statements 1 and 7 are intentionally the same query as
the baseline. Statements 2–6 can be tried independently of index setup.

### Execute reports

To execute all seven candidates sequentially:

```sql
SOURCE olap_queries_optimized.sql;
```

For control over which runs next, copy just one complete statement from the file
and execute it in Workbench or paste it at `mysql>`. Keep the connection/laptop
awake. There are no schema rebuilds, fact reloads, table deletions, server-setting
changes, or automatic result exports in this file.

## Validation and limitations

Implemented tests compare each candidate's exact output aliases and unordered
result rows with its baseline using synthetic CTEs that shadow every warehouse
table. Cases include NULL measurements, zero/negative values, all category
boundaries, missing dimension matches, empty input, shared zone names, unequal
group sizes, multiple active dates, and multiple minute IDs in the same hour.
Tests execute in read-only transactions. Real tables are used only for plain
EXPLAIN, never EXPLAIN ANALYZE or full-data equivalence scans.

Run these bounded checks from CMD using the existing project environment:

```cmd
set NYC_ETL_READONLY_TESTS=1
python -m unittest discover -s tests -p test_olap_optimized.py -v
set NYC_ETL_READONLY_TESTS=
```

The checks passed against local MySQL 8.0.43 with ONLY_FULL_GROUP_BY enabled.
There is no measured full-data speedup claim. Your teammate should inspect actual
outputs and record ordinary execution times when running the reports. Sorting
ties need not have identical row order. Baseline/optimized results must agree in
counts, NULLs, rounded measurements, and subtotals before final analytical use.

References: [MySQL indexes](https://dev.mysql.com/doc/refman/8.0/en/optimization-indexes.html),
[CTE materialization](https://dev.mysql.com/doc/refman/8.0/en/derived-table-optimization.html),
[EXPLAIN versus EXPLAIN ANALYZE](https://dev.mysql.com/doc/refman/8.0/en/explain.html).
