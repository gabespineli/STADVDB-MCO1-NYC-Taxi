# STADVDB MCO1 - NYC Taxi Data Loader

Python pipeline to import monthly NYC Yellow Taxi parquet datasets into a MySQL database.

## Prerequisites

- Python 3.9+
- A running MySQL 8 instance and an existing database (default: `source_db`)
- MySQL server setting `local_infile=ON` and an account with `CREATE`, `SELECT`, and `INSERT` privileges in that database
- Parquet files located inside the `parquet_data/` directory

---

## Installation

Install the required Python dependencies:

```bash
pip install pandas pyarrow sqlalchemy pymysql python-dotenv tqdm
```

Or install using `requirements.txt`:

```bash
pip install -r requirements.txt
```

---

## Configuration

1. Copy the example environment file:
   ```bash
   Copy-Item .env.example .env
   ```
2. Update the credentials in `.env` to match your local MySQL configuration:
   ```env
   DB_USER=root
   DB_PASSWORD=yourpassword
   DB_HOST=localhost
   DB_PORT=3306
   DB_NAME=source_db
   DB_TABLE=yellow_taxi_trips
   CHUNKSIZE=50000
   ```

---

## Usage

Run the data loading script:

```bash
python load_parquet_to_mysql.py
```

### Script Behavior:
- Automatically scans all `.parquet` files in the `parquet_data/` directory in alphabetical/chronological order.
- Processes the monthly files sequentially. For all 12 months, place `yellow_tripdata_2025-01.parquet` through `yellow_tripdata_2025-12.parquet` in that directory. The script imports every `.parquet` file found, so keep unrelated files elsewhere.
- Reads at most `CHUNKSIZE` rows per Arrow batch (default: `50,000`), writes one reusable temporary TSV file, and sends it through `LOAD DATA LOCAL INFILE`. Memory scales with batch size and Parquet decoding buffers rather than an entire month. No GPU is used.
- Displays the filename, loaded rows, elapsed time, and rows/second. Progress within a month is provisional until the final **Committed** message.
- Creates the raw destination table if missing, using the Parquet column names and compatible SQL types. Existing tables are never replaced or altered. Dimensions, facts, ETL scripts, and OLAP queries are unchanged.
- Uses MySQL text escaping and `\N` for SQL NULL. Integers and decimals do not pass through pandas or floating-point conversion; floats use round-trip text and `DOUBLE`. Timestamp fractions are retained up to MySQL's six-digit limit. Incompatible existing column types, precision loss, unsupported types, nonfinite numbers, MySQL warnings, or unexpected row counts stop the import.
- Creates a small InnoDB table, `_parquet_imports`, alongside the raw table. It records the destination, filename, SHA-256 checksum, row count, and completion time. Completed files are skipped on rerun, including byte-identical files renamed after import. A completed filename with changed contents is rejected.
- Commits **one month at a time**, with that month's completion record in the same transaction. An error or interruption rolls back the unfinished month; rerunning skips earlier completed months and retries the failed month from the beginning. A connection lost during commit is resolved by checking the history on rerun. One importer per destination can run at a time.
- Refuses to append to a nonempty raw table with no import history. If you previously used the old importer, reconcile those existing imports first, or use a separate empty raw table via `DB_TABLE` for a fresh rehearsal. It cannot infer which months the old script completed. Do not remove history independently of its raw data, modify source files during loading, or use another loader to write to the same target concurrently. Tracking prevents repeated file imports; it preserves duplicate rows already present in the source.

### Before importing all 12 months

1. Confirm `.env` points to the intended database and **raw** table. Back up existing data. Both the destination and history tables must use InnoDB for rollback.
2. Check the server setting in MySQL:
   ```sql
   SHOW GLOBAL VARIABLES LIKE 'local_infile';
   ```
   If it is `OFF`, enable it yourself using an administrative connection:
   ```sql
   SET GLOBAL local_infile = ON;
   ```
   To retain it across restarts, set `local_infile=ON` under `[mysqld]` in your MySQL configuration (`my.ini` on Windows). The Python client enables its own local-loading option automatically. The importer never changes global server settings. See [MySQL's LOCAL loading documentation](https://dev.mysql.com/doc/refman/8.0/en/load-data-local-security.html).
3. Check free space for the raw data, indexes, MySQL temporary files, and InnoDB undo/redo logs. Python uses only a batch-sized temporary file, but the monthly transaction can require substantial MySQL disk space; rollback may take time. `CHUNKSIZE` limits Python batch memory, not the transaction size. Start at `50000`; lower it if memory is tight while MySQL is running.
4. Rehearse one month against an empty test destination by temporarily setting `DB_TABLE` to a test raw table in `.env`, then run:
   ```bash
   python load_parquet_to_mysql.py --file yellow_tripdata_2025-01.parquet
   ```
   Check its row count against the Parquet metadata and `_parquet_imports`, and compare representative NULLs, integer IDs, amounts, and timestamps with the source. Run the same command again and confirm it reports **Skipped** and the count stays unchanged. Restore `DB_TABLE` before loading your intended destination.

After those checks, run `python load_parquet_to_mysql.py` to process all monthly files. Keep the laptop awake during the import. Actual speed depends on the CPU, disk, and MySQL configuration; no fixed speedup is assumed.

### Importer checks (no database required)

```bash
python -m unittest discover -s tests -v
```

## Build the warehouse after the raw import

The six tables in `schema.sql` match the project diagram: five dimensions,
21 fact columns, and eight foreign keys. The schema and `olap_queries.sql` have
not been redesigned. The Python raw importer is unchanged.

Use a **fresh MySQL Workbench connection** to `source_db`, with autocommit,
foreign-key checks, and unique checks enabled, and no open transaction. The SQL
uses MySQL 8.0.19+ syntax (checked against the laptop's MySQL 8.0.43).
The account needs the normal table privileges plus CREATE VIEW, CREATE ROUTINE,
ALTER ROUTINE (for replacing the routines), and EXECUTE. No administrative logging
privileges are needed. Stop and resolve any script error before proceeding.

### Run these files in order

| Order | File | What happens |
| --- | --- | --- |
| 1 | `schema.sql` | Creates the empty warehouse. **Initial setup only: it drops existing warehouse tables.** It does not drop raw trips or raw-import history. |
| 2 | `load_star_schema.sql` | Installs `etl_trip_source_2025` and two ETL procedures. **Does not load rows.** |
| 3 | `seed_dimensions.sql` | Calls `SeedTaxiDimensions2025()` to populate dimensions in a transaction. |
| 4 | Inspect the dimensions | On a fresh warehouse, expect 1,440 time rows, 366 date rows, 266 location rows, seven payment rows, and seven rate-code rows. Check their values too. |
| 5 | `load_fact.sql` | Calls `LoadTaxiFacts2025()` for one atomic full fact load. It refuses a nonempty destination. |
| 6 | `star_schema_checker.sql` | Read-only, full-population counts, all-measure sums/NULL counts, eight orphan checks, dimension labels, and a joined preview. |
| 7 | Student-authored `olap_queries.sql` | Run individual reports only after accepting the warehouse checks. Dashboard query sign-off remains a separate step. |

Do not run `load_star_scehma_recurssive.sql` or `load_fact_batched.sql`: they now
raise an explanatory error. Older Downloads copies are not the active ETL. Do not
run another fact loader after `load_fact.sql`, or let other tools write facts while
this pipeline runs. The raw import is already a separate completed stage.

### Analysis policy implemented in ETL

The time periods are mutually exclusive local NYC clock windows:

| Period | Hours |
| --- | --- |
| Late Night | 20:00-23:59 and 00:00-05:59 |
| Morning Rush | 06:00-09:59 |
| Midday | 10:00-15:59 |
| Evening Rush | 16:00-19:59 |

The overnight and evening windows follow [TLC taxi timing](https://www.nyc.gov/site/tlc/passengers/taxi-fare.page).
The morning window is an inferred analysis convention, consistent with a broad
6-10 a.m. commute period; it is not an official morning taxi-surcharge rule.
`dim_time` contains time-only labels on every day. Q3's existing weekday filter
supplies weekday scope; holidays are not separately excluded by this model.
No separate `Rush Hour` label is needed because Q3 accepts either rush label.

- Accept pickups **on or after 2025-01-01 and before 2026-01-01**.
- Require both timestamps, drop-off strictly after pickup, and no more than
  24 hours between them. Require 1-86,400 whole seconds because the diagram stores
  integer duration. A positive trip shorter than one second is excluded.
- Retain valid New Year's Eve trips ending on 2026-01-01. The date dimension has
  366 days, 2025-01-01 through 2026-01-01 inclusive.
- This 24-hour cutoff is a project data-quality rule, not a claim that TLC rejects
  such records. Historical timestamp anomalies are excluded by the pickup rule.
- Use timestamps as supplied, without UTC conversion. Local wall-clock duration
  cannot resolve ambiguous daylight-saving timestamps without source offsets.
- Preserve NULL monetary measures and signed refund/adjustment amounts. Convert
  to the diagram's two-decimal DECIMAL types; higher source precision remains in
  the untouched raw table. Conversion errors/warnings abort the fact transaction.
- Retain a trip with missing or negative distance, storing distance and speed as
  NULL when distance is negative/missing. Genuine zero distance produces zero speed.
  A derived speed that cannot fit DECIMAL(6,2) becomes NULL. Representable speeds
  above 100 mph remain visible and are flagged by the checker, not silently capped.
- Preserve payment 0 as **Flex Fare**. Missing/unrecognized payment maps to existing
  TLC code 5 (**Unknown**); missing/unrecognized rate maps to 99 (**Null/unknown**).
- Map missing/out-of-range location IDs to the explicit unknown location 0.
  Source IDs remain available in raw data. IDs 1-265 use the pinned
  [official lookup](https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv)
  in `reference_data/taxi_zone_lookup.csv`, including literal official `N/A` values.

`etl_trip_source_2025` centralizes population, code mappings, NULL treatment, and
DECIMAL conversions. Both the fact load and reconciliation read it, preventing
checker/loader population drift. It is an ETL support view, not another dimension
or a raw-data reporting shortcut.

### Loading, recovery, and checks

The loader keeps foreign-key and unique checks enabled, uses strict numeric
assignment, and uses READ COMMITTED for its transaction. Destination writes still
require locks; no setting guarantees a particular speed or eliminates every
resource limit. No binary/redo logging is disabled. Installation restores the
previous SQL mode; the seed restores its recursion-depth setting. Use this installer
only for initial setup, not for changing transformation definitions behind an
already populated warehouse.

Seed and fact procedures share a named lock so cooperating loads cannot overlap.
Dimensions cannot be reseeded once facts exist. The fact load is a single
transaction and does not use LIMIT/OFFSET or an automatic restart position.
Failures before commit roll back the fact insert and release the lock; rollback
can take time. A disconnected client can leave the server working temporarily.
Check the server's active sessions and fact-table state before retrying; a
nonempty table blocks accidental append even after an uncertain successful commit.
Do not delete records, rerun schema.sql, or discard raw-import history as a recovery
shortcut. Identical records already in the source are preserved as separate rows.

After a successful load, the procedure reports imported rows, elapsed seconds,
and average rows/second. During the large statement there is no reliable percent
complete; use Workbench/process-list status instead. Keep the laptop awake and
retain free space for the fact table, indexes, redo/undo, and temporary storage.
No full import was performed while implementing this pipeline.

Run the checker with raw/fact writers stopped. Eligible-source and fact counts,
all measure sums, and all NULL counts must agree, and all eight orphan counts
must be zero. Investigate flagged speeds rather than treating a preview as proof
of full data quality. The checker scans large tables and can take substantial time.

Offline checks (no database access):

```powershell
python -m unittest discover -s tests -v
```

Optional small **read-only** MySQL checks, using the same `.env`:

```powershell
$env:NYC_ETL_READONLY_TESTS = "1"
python -m unittest discover -s tests -p test_warehouse_etl.py -v
Remove-Item Env:NYC_ETL_READONLY_TESTS
```

These tests validate minute/date generation and the actual transformation SELECT
against synthetic CTE rows. They use PREPARE without EXECUTE to check procedure
grammar. They do not create schema objects or perform inserts. A complete stored
procedure execution/rollback rehearsal and production-sized timing remain separate
validation steps; no full warehouse import is automated by tests.

## Optimized OLAP candidates

The unchanged baseline remains in `olap_queries.sql`. Seven candidates in the
same order are provided in [olap_queries_optimized.sql](olap_queries_optimized.sql).
Statements 2–6 use query reformulation; statements 1 and 7 retain the original SQL
and use optional covering indexes from [olap_indexes.sql](olap_indexes.sql).
Neither index is created automatically. Index creation needs additional disk space
and should only be run once for missing indexes, separately from report execution.

See [OLAP_OPTIMIZATION.md](OLAP_OPTIMIZATION.md) for the per-query changes,
Workbench/MySQL commands, completed read-only checks, and storage precautions.
The removed `reports/` runner is not required and has not been recreated.
The dashboard now connects all seven team-approved statements unchanged.
Team-supplied benchmark runtimes appear in its registry.

## Analytics dashboard (Streamlit)

**Current integration:** all seven completed optimized statements are connected.
See **[dashboard/RUNNING.md](dashboard/RUNNING.md)** for current startup,
read-only account, long-query caching, and ngrok instructions, and
[dashboard/VERIFICATION.md](dashboard/VERIFICATION.md) for checks and limitations.

The dashboard is a separate presentation layer in `dashboard/`. It does not modify
or run the raw importer, schema, ETL scripts, or root `olap_queries.sql`.

From this repository directory on Windows:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run dashboard/app.py
```

Open **http://127.0.0.1:8501**. Streamlit and Plotly are the only new direct Python
dependencies. Recent Streamlit releases require a newer Python than the importer's
Python 3.9 minimum; Python **3.10+** is recommended for the dashboard (tested here
with Python 3.14). Run the command in your existing environment if it is compatible.

If port 8501 is already occupied, use
`python -m streamlit run dashboard/app.py --server.port 8502` and open
**http://127.0.0.1:8502** instead. Use that same port in any later ngrok command.

### What works now

- Separate Q1 demand, Q2 payment/fare, and Q3 travel-efficiency sections, with seven
  report views matching the existing OLAP output aliases.
- Plotly charts, detailed aggregated result tables, classified CSV downloads, and
  prominent synthetic-sample labels. Sample reports are independent UI fixtures;
  they are not actual NYC findings or an approved time-classification policy.
- Read-only MySQL connectivity and warehouse availability checks, using table
  metadata and `LIMIT 1` checks on the six fixed warehouse tables. No raw trip
  records or expensive full-table counts are used to test connectivity.
- Cached engines, 60-second availability checks, and 24-hour report results.
  Analytical reports run only after the user selects Load warehouse report. The
  database defaults to a five-second connection timeout and a configurable
  7,200-second socket read timeout;
  the latter is not a guaranteed server-side query execution deadline.
- Graceful unavailable, missing-table, empty-result, and query-error states. A live
  failure or empty result never silently becomes sample data.

### Saved results for presentations

The default **Saved exports** mode reads completed aggregate reports from
`dashboard/exports/` without connecting to MySQL. It opens an available report first
when a complete export exists. Your teammate can execute queries separately;
copy each final timestamped TSV and its matching SUCCESS log into that folder,
then choose **Refresh saved results**. Follow the filename, column, and completion
metadata format in [dashboard/exports/README.md](dashboard/exports/README.md).
Query execution is managed by your team separately; the original analytical SQL
remains in `olap_queries.sql`. Reports without a completed export show an awaiting-results state.
Partial, failed, unpaired, or row-count-mismatched exports are not presented as
completed results. A successful export is explicitly marked as awaiting analytical
review; it is not an approval of the SQL or the underlying data quality.

Saved-result controls select existing borough, zone, period, category, and hour
groups only where those fields exist. Q3 location results support a minimum trip
count per group, duration/speed charts, and a logarithmic axis. Outlier warnings
and flagged rows remain visible; filtering does not alter source files. There is
no month/date filter for exports that do not contain that breakdown. The dashboard
never averages the exported averages together. Downloads identify the filtered
view or the complete export; literal `N/A` labels and SQL NULL (`\N`) are preserved.

Use **Sample preview** for synthetic layout demonstrations or **Warehouse reports**
for the existing explicitly approved SQL integration. Database presence checks now
run only in warehouse mode. No new dependencies or SQL changes are required.

### Live database configuration and safety

The app reads the repository-root `.env` and existing `DB_USER`, `DB_PASSWORD`,
`DB_HOST`, `DB_PORT`, and `DB_NAME` settings. `DB_TABLE` is intentionally unused:
raw source tables and benchmark tables are not dashboard reporting inputs.

For a separate warehouse schema or a dedicated SELECT-only login, optionally set
`DASHBOARD_DB_NAME`, `DASHBOARD_DB_USER`, `DASHBOARD_DB_PASSWORD`,
`DASHBOARD_DB_HOST`, and `DASHBOARD_DB_PORT`. Each override falls back to its
corresponding existing setting; there is no automatic database creation or migration.
Have your database administrator provision a dedicated account with direct
SELECT-only grants on the warehouse tables. Live execution refuses root and
unverified privileges; no users or grants are created automatically.

All reads execute in MySQL read-only transactions. Trusted local report SQL also
passes a conservative single-statement/warehouse-table guard. This is not a SQL
sandbox or a substitute for account privileges. No database credentials or original
driver exceptions are rendered in the UI. `.env` remains Git-ignored. No tokens or
passwords belong in `reports.json`, SQL files, or downloaded CSVs.

### Approved SQL and parameter scope

All seven entries now select their approved statement directly from the unchanged
root `olap_queries_optimized.sql`, with a file fingerprint, population, grain, and
team-supplied runtime. The live-report interface requires a verified SELECT-only
account and populated warehouse tables. Reports that depend on
late-night/rush-hour classifications or real geography also check those prerequisites.

Borough, zone, month/date range, time period, fare range, distance category, and
aggregation controls are prepared for live SQL integration; they are hidden until
a report has approved bindings. Saved-export controls are separate and only select
existing result groups. Sample previews do not pretend SQL filters are implemented.

The seven current statements contain no bind parameters. Database population
filters and alternate aggregation levels therefore require student-authored SQL
changes before they can be enabled. Separate display controls only select returned
groups. Follow **[dashboard/queries/README.md](dashboard/queries/README.md)** for
future team-approved revisions. No analytical SQL was generated or modified.

Use **Refresh database status** after warehouse changes. To refresh report data,
select Load warehouse report again; identical requests can use the 24-hour cache.
Use Refresh from MySQL for an explicit fresh execution. Chart interactions do not
execute SQL, and only one expensive report runs at a time in this app process.
Restart Streamlit after changing database credentials or environment configuration.

### Sharing later through ngrok

The app binds to localhost by default. Nothing automatically opens a public tunnel.
Install the [official ngrok CLI](https://ngrok.com/docs/start) separately, complete its account/token setup locally,
and, only when you are ready to share, leave Streamlit running and run this in a
second terminal:

```powershell
ngrok http 8501
```

Share the forwarding HTTPS URL and stop the ngrok process when the presentation
ends. Ngrok is not a required Python library. Keep Streamlit's default CORS/XSRF
protections enabled. Anyone with an unrestricted tunnel URL can view the dashboard;
use ngrok access controls if the audience must be restricted. No tunnel was started
as part of this setup.

### Dashboard code map

| Location | Responsibility |
| --- | --- |
| `dashboard/app.py` | Navigation, source mode, report loading, and visible status |
| `dashboard/config.py`, `dashboard/db.py` | Environment settings, read-only connections, lightweight checks, cached query execution |
| `dashboard/reports.py`, `dashboard/reports.json` | Seven output contracts, validation flags, and approved parameter mappings |
| `dashboard/filters.py`, `dashboard/charts.py` | Reusable controls and Plotly views |
| `dashboard/sections/` | Q1, Q2, Q3, and shared result/table/export presentation |
| `dashboard/sample_data.py` | Explicitly synthetic result fixtures |
| `dashboard/queries/README.md` | OLAP integration handoff; no generated analytical SQL |
| `.streamlit/config.toml`, `dashboard/style.css` | Local binding, telemetry preference, and presentation styling |
