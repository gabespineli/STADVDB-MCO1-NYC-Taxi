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

## Analytics dashboard (Streamlit)

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
- Cached engines, 60-second availability checks, and five-minute report results.
  Analytical reports run only after the user selects Load warehouse report. The
  database has a five-second connection timeout and a 30-second socket read timeout;
  the latter is not a guaranteed server-side query execution deadline.
- Graceful unavailable, missing-table, empty-result, and query-error states. A live
  failure or empty result never silently becomes sample data.

### Database configuration and safety

The app reads the repository-root `.env` and existing `DB_USER`, `DB_PASSWORD`,
`DB_HOST`, `DB_PORT`, and `DB_NAME` settings. `DB_TABLE` is intentionally unused:
raw source tables and benchmark tables are not dashboard reporting inputs.

For a separate warehouse schema or a dedicated SELECT-only login, optionally set
`DASHBOARD_DB_NAME`, `DASHBOARD_DB_USER`, `DASHBOARD_DB_PASSWORD`,
`DASHBOARD_DB_HOST`, and `DASHBOARD_DB_PORT`. Each override falls back to its
corresponding existing setting; there is no automatic database creation or migration.
Have your database administrator provision a SELECT-only account for presentation
use; do not grant raw-table access to that account if it is unnecessary.

All reads execute in MySQL read-only transactions. Trusted local report SQL also
passes a conservative single-statement/warehouse-table guard. This is not a SQL
sandbox or a substitute for account privileges. No database credentials or original
driver exceptions are rendered in the UI. `.env` remains Git-ignored. No tokens or
passwords belong in `reports.json`, SQL files, or downloaded CSVs.

### What is waiting for your teammates

All seven report entries start with `validated: false`. The live-report interface
remains blocked until the warehouse tables contain records and the OLAP teammate
supplies and approves the corresponding aggregated SQL. Reports that depend on
late-night/rush-hour classifications or real geography also check those prerequisites.

Borough, zone, month/date range, time period, fare range, distance category, and
aggregation controls are prepared but disabled until a report has approved SQL
bindings for them. Sample previews do not pretend those filters are implemented.

Follow **[dashboard/queries/README.md](dashboard/queries/README.md)** to integrate
the seven student-authored statements. Put one finalized statement in each named
file in `dashboard/queries/`, preserving its result aliases, and approve its
population, grain, aggregated status, and supported filter bindings in
`dashboard/reports.json`. No analytical SQL has been generated for this setup.

Use **Refresh database status** after warehouse changes. To refresh report data,
select Load warehouse report again; identical requests can use the five-minute cache.
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
