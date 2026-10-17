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
