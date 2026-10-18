"""Read completed aggregate exports. Never execute SQL or load partial files."""

from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
import re

import pandas as pd
import streamlit as st

from dashboard.config import MAX_REPORT_ROWS, ROOT
from dashboard.reports import validate_result

RESULTS = ROOT / "dashboard" / "exports"
EXPORT_NAMES = {
    "q1_demand": "q1_zone_borough", "q1_hourly": "q1_hourly",
    "q1_monthly": "q1_monthly", "q2_fare": "q2_fare_payment",
    "q2_payment": "q2_borough_time", "q3_comparison": "q3_rush_offpeak",
    "q3_location": "q3_midrange",
}


@dataclass(frozen=True)
class Export:
    path: str
    filename: str
    exported_at: str
    rows: int
    seconds: float
    size: int
    modified: int


def completed_exports(report_id, directory=None):
    """A successful companion log and a final filename are both required."""
    root = Path(directory) if directory is not None else RESULTS
    prefix = EXPORT_NAMES[report_id]
    exports = []
    for path in root.glob(prefix + "_*.tsv"):
        match = re.fullmatch(re.escape(prefix) + r"_(\d{8}_\d{6})_\d{6}\.tsv", path.name)
        if not match or path.is_symlink():
            continue
        try:
            log = path.with_suffix(".log").read_text(encoding="utf-8-sig")
            if not log.startswith("SUCCESS\n") or f"Report: {prefix}\n" not in log:
                continue
            rows = int(re.search(r"(?m)^Rows: (\d+)$", log).group(1))
            seconds = float(re.search(r"(?m)^Elapsed seconds: ([\d.]+)$", log).group(1))
            exported_at = datetime.strptime(match[1], "%Y%m%d_%H%M%S").strftime("%d %b %Y · %H:%M")
            stat = path.stat()
            exports.append(Export(str(path), path.name, exported_at, rows, seconds,
                                  stat.st_size, stat.st_mtime_ns))
        except (OSError, ValueError, AttributeError):
            continue
    return sorted(exports, key=lambda export: export.filename, reverse=True)


@st.cache_data(show_spinner=False, max_entries=14)
def load_export(report, export):
    path = Path(export.path)
    if export.size > 25 * 1024 * 1024:
        raise ValueError("This export is too large for an aggregated report (25 MB limit).")
    try:
        payload = path.read_bytes()
        from io import BytesIO
        # Keep literal NYC lookup labels such as N/A; only \N means SQL NULL.
        data = pd.read_csv(BytesIO(payload), sep="\t", encoding="utf-8-sig",
                           dtype=str, keep_default_na=False, na_values=["\\N"],
                           nrows=MAX_REPORT_ROWS + 1)
    except (OSError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError):
        raise ValueError("The export could not be read. Copy the completed TSV and its SUCCESS log again.") from None
    if len(data) > MAX_REPORT_ROWS:
        raise ValueError(f"The export exceeds {MAX_REPORT_ROWS:,} aggregated rows.")
    if len(data) != export.rows:
        raise ValueError("The export row count differs from its completion log. Use a complete matching TSV/log pair.")
    data = validate_result(report, data)
    if report.id == "q3_location" and data.duplicated(["borough", "zone", "time_period", "hour"]).any():
        raise ValueError("The location export contains duplicate result groups. Ask the query author to review it.")
    return {"data": data, "filename": export.filename, "exported_at": export.exported_at,
            "seconds": export.seconds, "sha256": hashlib.sha256(payload).hexdigest()}
