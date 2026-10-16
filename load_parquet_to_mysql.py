import os
from glob import glob
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
from tqdm import tqdm

# Load settings from .env file if available
load_dotenv()

DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "yourpassword")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "source_db")
DB_TABLE = os.getenv("DB_TABLE", "yellow_taxi_trips")
CHUNKSIZE = int(os.getenv("CHUNKSIZE", "50000"))

PARQUET_DIR = Path(__file__).parent / "parquet_data"


def get_db_engine():
    connection_url = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    return create_engine(connection_url)


def load_parquet_files_to_mysql():
    files = sorted(glob(str(PARQUET_DIR / "*.parquet")))

    if not files:
        print(f"No parquet files found in {PARQUET_DIR}")
        return

    print(f"Found {len(files)} parquet files to import into table '{DB_TABLE}'.")

    engine = get_db_engine()

    total_rows = 0

    for idx, filepath in enumerate(files, start=1):
        filename = Path(filepath).name
        print(f"\n[{idx}/{len(files)}] Processing: {filename}...")

        # Read parquet file into DataFrame
        df = pd.read_parquet(filepath)
        num_rows = len(df)
        print(f"  -> Read {num_rows:,} rows from {filename}")

        # Determine table action:
        # First file replaces the table if it already exists, subsequent files append.
        if_exists_mode = "replace" if idx == 1 else "append"

        print(
            f"  -> Uploading to MySQL table '{DB_TABLE}' (mode='{if_exists_mode}', chunksize={CHUNKSIZE:,})..."
        )
        with tqdm(total=num_rows, unit="rows", desc=f"  Progress ({filename})") as pbar:
            # Chunking to avoid memory issues and MySQL max_allowed_packet limits
            for chunk_start in range(0, num_rows, CHUNKSIZE):
                chunk = df.iloc[chunk_start : chunk_start + CHUNKSIZE]
                chunk_mode = if_exists_mode if chunk_start == 0 else "append"
                chunk.to_sql(
                    DB_TABLE,
                    con=engine,
                    if_exists=chunk_mode,
                    index=False,
                    method="multi",
                )
                pbar.update(len(chunk))

        total_rows += num_rows
        print(f"  -> Successfully loaded {filename}.")

    print(
        f"\nAll {len(files)} files were successfully imported into '{DB_TABLE}'! Total rows loaded: {total_rows:,}"
    )


if __name__ == "__main__":
    load_parquet_files_to_mysql()
