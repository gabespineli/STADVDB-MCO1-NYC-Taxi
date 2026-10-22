"""Publish validated aggregate snapshots for the separate local React app.

Uses the existing readers, definitions, and official map join. No SQL execution,
credentials, sample fallbacks, or new Python dependencies.
"""

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
sys.path.insert(0, str(ROOT))

from plotly.offline import get_plotlyjs

from dashboard.analytics import detail_rows
from dashboard.geography import load_geography, match_groups
from dashboard.presentation import CAUTIONS, SCOPES
from dashboard.reports import REPORTS
from dashboard.snapshots import completed_exports, load_export


def prepare(destination=APP / "public" / "data"):
    destination.mkdir(parents=True, exist_ok=True)
    snapshot = {"generatedAt": datetime.now(timezone.utc).isoformat(), "period": "2025",
                "reports": {}, "mapAvailable": False}
    geojson, lookup = None, None
    try:
        geojson, lookup = load_geography.__wrapped__()
        (destination / "taxi-zones.json").write_text(json.dumps(geojson, separators=(",", ":")), encoding="utf-8")
        snapshot["mapAvailable"] = True
    except ValueError as error:
        print(f"Map unavailable: {error}")
    download_dir = destination / "exports"
    download_dir.mkdir(exist_ok=True)
    for report in REPORTS:
        entry = {"id": report.id, "section": report.section, "title": report.title,
                 "scope": SCOPES[report.id], "caution": CAUTIONS[report.id],
                 "columns": list(report.columns), "rows": [], "source": None,
                 "status": "Awaiting a completed export."}
        exports = completed_exports(report.id)
        if exports:
            try:
                result = load_export.__wrapped__(report, exports[0])
                data = result["data"]
                # Pandas' JSON writer produces standard JSON null, never NaN.
                entry["rows"] = json.loads(data.to_json(orient="records", double_precision=12))
                entry["source"] = {key: result[key] for key in ("filename", "exported_at", "sha256")}
                entry["source"]["rowCount"] = len(data)
                entry["status"] = "Ready"
                shutil.copyfile(exports[0].path, download_dir / exports[0].filename)
                if report.id == "q1_demand" and geojson is not None:
                    joined = match_groups(detail_rows(data), lookup, geojson)
                    entry["mapRows"] = json.loads(joined.to_json(orient="records"))
            except ValueError as error:
                entry["status"] = str(error)
        snapshot["reports"][report.id] = entry
        print(f"{report.id}: {entry['status']} ({len(entry['rows']):,} groups)")
    # The installed Python Plotly package supplies the browser runtime locally.
    # No CDN or separate JavaScript Plotly download is needed.
    (destination / "plotly.min.js").write_text(get_plotlyjs(), encoding="utf-8")
    temporary = destination / "snapshot.partial.json"
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, allow_nan=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(destination / "snapshot.json")
    return snapshot


if __name__ == "__main__":
    result = prepare()
    ready = sum(report["status"] == "Ready" for report in result["reports"].values())
    print(f"Prepared {ready}/7 saved reports for React.")
