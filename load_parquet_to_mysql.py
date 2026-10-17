"""Load monthly raw Parquet files without replacing tables or repeating imports."""

import argparse
import hashlib
import math
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

import pyarrow as pa
import pyarrow.parquet as pq
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from tqdm import tqdm

load_dotenv()

DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "yourpassword")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "source_db")
DB_TABLE = os.getenv("DB_TABLE", "yellow_taxi_trips")
CHUNKSIZE = int(os.getenv("CHUNKSIZE", "50000"))
PARQUET_DIR = Path(__file__).resolve().parent / "parquet_data"
IMPORT_TABLE = "_parquet_imports"


def quote_identifier(name):
    if not name or len(name) > 64 or "\x00" in name:
        raise ValueError(f"Invalid MySQL identifier: {name!r}")
    return "`" + name.replace("`", "``") + "`"


def get_db_engine():
    # URL.create also handles passwords containing @, /, : or other URL characters.
    return create_engine(
        URL.create("mysql+pymysql", username=DB_USER, password=DB_PASSWORD,
                   host=DB_HOST, port=int(DB_PORT), database=DB_NAME),
        connect_args={"local_infile": True, "charset": "utf8mb4"},
    )


def mysql_type(arrow_type):
    """Keep raw values in native SQL types; never infer types through pandas."""
    if pa.types.is_boolean(arrow_type):
        return "TINYINT"
    if pa.types.is_integer(arrow_type):
        return "BIGINT UNSIGNED" if pa.types.is_unsigned_integer(arrow_type) else "BIGINT"
    if pa.types.is_floating(arrow_type):
        return "DOUBLE"
    if pa.types.is_decimal(arrow_type):
        if not 0 <= arrow_type.scale <= min(30, arrow_type.precision) or arrow_type.precision > 65:
            raise ValueError(f"Cannot preserve {arrow_type} in a MySQL DECIMAL")
        return f"DECIMAL({arrow_type.precision},{arrow_type.scale})"
    if pa.types.is_timestamp(arrow_type) and arrow_type.tz is None:
        return "DATETIME(6)"
    if pa.types.is_date(arrow_type):
        return "DATE"
    if pa.types.is_string(arrow_type) or pa.types.is_large_string(arrow_type):
        return "LONGTEXT"
    raise ValueError(f"Unsupported Parquet type: {arrow_type}")


def require_innodb(cursor, table):
    cursor.execute(
        "SELECT ENGINE FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s", (DB_NAME, table),
    )
    row = cursor.fetchone()
    if row is None or row[0] != "InnoDB":
        raise RuntimeError(f"{table} must be an InnoDB table for safe rollback")


def prepare_tables(cursor, schema):
    """Create missing raw/history tables only; never change existing definitions."""
    if DB_TABLE.casefold() == IMPORT_TABLE.casefold():
        raise ValueError(f"DB_TABLE cannot be {IMPORT_TABLE}")
    columns = ", ".join(
        f"{quote_identifier(field.name)} {mysql_type(field.type)} NULL" for field in schema
    )
    cursor.execute(
        f"CREATE TABLE IF NOT EXISTS {quote_identifier(DB_TABLE)} ({columns}) "
        "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
    )
    cursor.execute(
        f"CREATE TABLE IF NOT EXISTS {quote_identifier(IMPORT_TABLE)} ("
        "target_table VARCHAR(64) NOT NULL, filename VARCHAR(255) NOT NULL, "
        "sha256 CHAR(64) NOT NULL, row_count BIGINT UNSIGNED NOT NULL, "
        "completed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "PRIMARY KEY (target_table, filename), UNIQUE KEY (target_table, sha256)"
        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin"
    )
    require_innodb(cursor, DB_TABLE)
    require_innodb(cursor, IMPORT_TABLE)
    cursor.execute(
        f"SELECT 1 FROM {quote_identifier(IMPORT_TABLE)} WHERE target_table = %s LIMIT 1",
        (DB_TABLE,),
    )
    if cursor.fetchone() is None:
        cursor.execute(f"SELECT 1 FROM {quote_identifier(DB_TABLE)} LIMIT 1")
        if cursor.fetchone() is not None:
            raise RuntimeError(
                "The destination already contains rows without import history. "
                "Stopping to avoid duplicating an older import. Reconcile those rows "
                "first, or use a separate empty raw table via DB_TABLE."
            )


def validate_columns(cursor, schema):
    cursor.execute(
        "SELECT COLUMN_NAME, DATA_TYPE, NUMERIC_PRECISION, NUMERIC_SCALE, DATETIME_PRECISION "
        "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
        (DB_NAME, DB_TABLE),
    )
    columns = {row[0]: row[1:] for row in cursor.fetchall()}
    if set(columns) != set(schema.names):
        raise ValueError(f"Parquet columns do not match the existing {DB_TABLE} columns")
    for field in schema:
        mysql_type(field.type)  # Reject unsupported input even for existing tables.
        data_type, precision, scale, _ = columns[field.name]
        if pa.types.is_integer(field.type) or pa.types.is_boolean(field.type):
            compatible = (data_type in {"tinyint", "smallint", "mediumint", "int", "bigint"}
                          or (data_type == "double" and scale is None))
        elif pa.types.is_floating(field.type):
            compatible = data_type == "double" and scale is None
        elif pa.types.is_decimal(field.type):
            compatible = (data_type == "decimal" and scale >= field.type.scale
                          and precision - scale >= field.type.precision - field.type.scale)
        elif pa.types.is_timestamp(field.type):
            compatible = data_type == "datetime"
        elif pa.types.is_date(field.type):
            compatible = data_type == "date"
        else:
            compatible = data_type in {"varchar", "tinytext", "text", "mediumtext", "longtext"}
        if not compatible:
            raise ValueError(
                f"{field.name}: {field.type} cannot be preserved in existing {data_type}. "
                "The importer will not alter your table."
            )
    return columns


# MySQL text format, not CSV: literal backslashes must be escaped before controls.
TEXT_ESCAPES = str.maketrans({"\\": "\\\\", "\t": "\\t", "\n": "\\n", "\r": "\\r",
                              "\x00": "\\0", "\x1a": "\\Z"})


def encode_value(value):
    if value is None:
        return r"\N"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("MySQL cannot preserve NaN or infinity; source NULLs are supported")
    # str(float) round-trips doubles; str(Decimal) retains decimal precision.
    return str(value).translate(TEXT_ESCAPES)


def write_batch(batch, path, columns):
    values = []
    for field, array in zip(batch.schema, batch.columns):
        if pa.types.is_timestamp(field.type):
            # Safe casting rejects nonzero nanoseconds instead of dropping precision.
            array = array.cast(pa.timestamp("us"), safe=True)
            fsp = columns[field.name][3] or 0
            column_values = array.to_pylist()
            if any(v is not None and v.microsecond % (10 ** (6 - fsp)) for v in column_values):
                raise ValueError(f"{field.name}: existing DATETIME({fsp}) would lose precision")
        else:
            column_values = array.to_pylist()
        # Older pandas-created tables may store nullable integer columns as DOUBLE.
        if pa.types.is_integer(field.type) and columns[field.name][0] == "double":
            if any(v is not None and int(float(v)) != v for v in column_values):
                raise ValueError(f"{field.name}: existing DOUBLE would lose integer precision")
        values.append(column_values)
    # The file is closed before MySQL opens it, which is required on Windows.
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.writelines("\t".join(encode_value(v) for v in row) + "\n" for row in zip(*values))


def load_batch(cursor, path, names, expected_rows):
    column_list = ", ".join(quote_identifier(name) for name in names)
    cursor.execute(
        f"LOAD DATA LOCAL INFILE %s INTO TABLE {quote_identifier(DB_TABLE)} "
        "CHARACTER SET utf8mb4 "
        r"FIELDS TERMINATED BY '\t' ESCAPED BY '\\' LINES TERMINATED BY '\n' "
        f"({column_list})", (path.resolve().as_posix(),),
    )
    inserted = cursor.rowcount
    # LOCAL can downgrade errors to warnings even with strict SQL mode enabled.
    cursor.execute("SHOW COUNT(*) WARNINGS")
    warning_count = cursor.fetchone()[0]
    if warning_count:
        cursor.execute("SHOW WARNINGS LIMIT 5")
        raise RuntimeError(f"LOAD DATA reported {warning_count} warning(s): {cursor.fetchall()!r}")
    if inserted != expected_rows:
        raise RuntimeError(f"Expected {expected_rows:,} rows, but MySQL inserted {inserted:,}")


def file_digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def import_file(connection, cursor, path, batch_path):
    started = perf_counter()
    print(f"  Checking file checksum: {path.name}", flush=True)
    before = path.stat()
    digest = file_digest(path)
    cursor.execute(
        f"SELECT filename, sha256, row_count FROM {quote_identifier(IMPORT_TABLE)} "
        "WHERE target_table = %s AND (filename = %s OR sha256 = %s)",
        (DB_TABLE, path.name, digest),
    )
    previous = cursor.fetchall()
    if any(row[1] != digest for row in previous):
        raise RuntimeError(f"{path.name} changed since its completed import; refusing to append it")
    if previous:
        connection.rollback()  # End the read-only transaction before the next file.
        print(f"  Skipped: already imported {previous[0][2]:,} rows ({previous[0][0]}).")
        return 0

    with pq.ParquetFile(path, pre_buffer=False) as parquet:
        columns = validate_columns(cursor, parquet.schema_arrow)
        rows = 0
        try:
            with tqdm(total=parquet.metadata.num_rows, unit="rows", unit_scale=True,
                      desc=path.name, mininterval=1) as progress:
                for batch in parquet.iter_batches(batch_size=CHUNKSIZE):
                    write_batch(batch, batch_path, columns)
                    load_batch(cursor, batch_path, batch.schema.names, batch.num_rows)
                    rows += batch.num_rows
                    progress.update(batch.num_rows)
                    del batch
            if rows != parquet.metadata.num_rows:
                raise RuntimeError("Imported row count differs from the Parquet metadata")
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise RuntimeError("Source file changed during import; keep Parquet files unchanged")
            cursor.execute(
                f"INSERT INTO {quote_identifier(IMPORT_TABLE)} "
                "(target_table, filename, sha256, row_count) VALUES (%s, %s, %s, %s)",
                (DB_TABLE, path.name, digest, rows),
            )
            # One transaction per month: data and its completion record commit together.
            connection.commit()
        except BaseException:
            print(f"\n  {path.name} did not finish. Rolling back its transaction.", flush=True)
            connection.rollback()
            raise
    elapsed = perf_counter() - started
    print(f"  Committed {rows:,} rows in {elapsed:.1f}s ({rows / max(elapsed, 0.001):,.0f} rows/s).")
    return rows


def load_parquet_files_to_mysql(filename=None):
    if CHUNKSIZE <= 0:
        raise ValueError("CHUNKSIZE must be a positive number of rows")
    quote_identifier(DB_TABLE)
    if filename is not None:
        if Path(filename).name != filename or not filename.endswith(".parquet"):
            raise ValueError("--file must be a Parquet filename inside parquet_data")
        files = [PARQUET_DIR / filename]
        if not files[0].is_file():
            raise FileNotFoundError(files[0])
    else:
        files = sorted(PARQUET_DIR.glob("*.parquet"))
    if not files:
        print(f"No parquet files found in {PARQUET_DIR}")
        return
    print(f"Found {len(files)} parquet files to import sequentially into '{DB_TABLE}'.")
    engine = get_db_engine()
    connection = None
    started = perf_counter()
    try:
        connection = engine.raw_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT @@GLOBAL.local_infile")
            if not cursor.fetchone()[0]:
                raise RuntimeError("MySQL local_infile is OFF. Enable it on your server before importing.")
            # SQL literals below use MySQL's standard backslash escaping.
            cursor.execute("SELECT @@SESSION.sql_mode")
            modes = set(filter(None, cursor.fetchone()[0].split(",")))
            modes.discard("NO_BACKSLASH_ESCAPES")
            modes.add("STRICT_TRANS_TABLES")
            cursor.execute("SET SESSION sql_mode = %s", (",".join(sorted(modes)),))
            # Serialize importer runs for this target. Closing the connection releases it.
            lock_name = hashlib.sha256(f"{DB_NAME}.{DB_TABLE}".casefold().encode()).hexdigest()
            cursor.execute("SELECT GET_LOCK(%s, 0)", (lock_name,))
            if cursor.fetchone()[0] != 1:
                raise RuntimeError("Another importer is already running for this destination")
            with pq.ParquetFile(files[0], pre_buffer=False) as first:
                prepare_tables(cursor, first.schema_arrow)
            connection.commit()  # DDL setup stays outside monthly data transactions.
            total_rows = 0
            with TemporaryDirectory(prefix="taxi-import-") as temp_dir:
                batch_path = Path(temp_dir) / "batch.tsv"
                for index, path in enumerate(files, start=1):
                    print(f"\n[{index}/{len(files)}] Processing: {path.name}", flush=True)
                    total_rows += import_file(connection, cursor, path, batch_path)
            print(f"\nFinished in {perf_counter() - started:.1f}s. Newly imported: {total_rows:,} rows.")
    finally:
        if connection is not None:
            connection.close()
        engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", help="Import one filename from parquet_data (default: all *.parquet)")
    args = parser.parse_args()
    try:
        load_parquet_files_to_mysql(args.file)
    except KeyboardInterrupt:
        print("\nImport interrupted. Rerun to skip completed files and retry the unfinished month.")
        sys.exit(130)
    except Exception as error:
        print(f"\nImport stopped: {error}", file=sys.stderr)
        sys.exit(1)
