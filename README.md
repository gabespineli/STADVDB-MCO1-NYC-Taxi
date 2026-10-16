# STADVDB MCO1 - NYC Taxi Data Loader

Python pipeline to import monthly NYC Yellow Taxi parquet datasets into a MySQL database.

## Prerequisites

- Python 3.9+
- A running MySQL database instance
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
   cp .env.example .env
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
- Creates or replaces the destination table upon processing the first file, then appends the remaining files.
- Inserts records in configurable chunks (default: `50,000` rows) with a live progress bar to optimize performance and prevent MySQL memory/packet overflows.
