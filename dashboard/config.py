"""Read project configuration without importing or running the raw loader."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE_TABLES = (
    "fact_trip_records", "dim_date", "dim_time", "dim_location", "dim_payment", "dim_rate_code",
)
MAX_REPORT_ROWS = 10000


@dataclass(frozen=True)
class DatabaseSettings:
    user: str
    password: str = field(repr=False)
    host: str = "localhost"
    port: int = 3306
    database: str = "source_db"


def database_settings():
    values = {**dotenv_values(ROOT / ".env"), **os.environ}

    def setting(name, default=""):
        return values.get("DASHBOARD_" + name) or values.get(name) or default

    try:
        port = int(setting("DB_PORT", "3306"))
        if not 1 <= port <= 65535:
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError("DB_PORT must be a valid TCP port") from None
    return DatabaseSettings(
        user=setting("DB_USER", "root"), password=setting("DB_PASSWORD"),
        host=setting("DB_HOST", "localhost"), port=port,
        database=setting("DB_NAME", "source_db"),
    )
