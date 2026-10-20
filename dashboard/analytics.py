"""Display-only transformations of approved aggregates; no SQL or pooled means."""

import pandas as pd

ROLLUP_LABELS = {
    "borough": {"ALL BOROUGHS"}, "zone": {"Borough Subtotal", "ALL ZONES"},
    "time_period": {"All Time Periods"}, "payment_method": {"All Payment Methods"},
    "fare_range": {"ALL FARE TIERS"}, "distance_bucket": {"All Distance Tiers"},
}


def detail_rows(data):
    result = data.copy()
    for column, labels in ROLLUP_LABELS.items():
        if column in result:
            result = result[result[column].notna() & ~result[column].isin(labels)]
    for column in ("yr", "qtr", "mo"):
        if column in result:
            result = result[pd.to_numeric(result[column], errors="coerce").notna()]
    return result


def payment_composition(data, dimensions, count="Trips"):
    """Percentages use the displayed, mutually exclusive payment counts."""
    result = data.copy()
    denominator = result.groupby(dimensions, dropna=False)[count].transform(lambda values: values.sum(min_count=len(values)))
    result["Share (%)"] = 100 * result[count] / denominator.where(denominator > 0)
    return result


def rush_differences(data):
    result = data.copy()
    result["Extra minutes"] = result.rush_hour_duration_min - result.off_peak_duration_min
    baseline = result.off_peak_duration_min.where(result.off_peak_duration_min > 0)
    result["Duration difference (%)"] = 100 * result["Extra minutes"] / baseline
    return result


def monthly_rows(data):
    result = detail_rows(data)
    result = result.copy()
    years = pd.to_numeric(result.yr, errors="coerce")
    months = pd.to_numeric(result.mo, errors="coerce")
    valid = years.notna() & months.between(1, 12)
    result = result[valid].copy()
    result["Month"] = pd.to_datetime(dict(year=years[valid].astype(int),
                                        month=months[valid].astype(int), day=1))
    return result


def monthly_totals(data):
    rows = monthly_rows(data)
    totals = rows.groupby("Month")["late_night_pickups"].sum(min_count=1)
    if not totals.empty:
        # Missing months are gaps, never invented zeros or connected lines.
        totals = totals.reindex(pd.date_range(totals.index.min(), totals.index.max(), freq="MS"))
    return totals.rename_axis("Month").reset_index()


def safe_heatmap(data, row, column, value, columns=None):
    """Reject ambiguous cells rather than silently averaging exported averages."""
    if data.duplicated([row, column]).any():
        raise ValueError("Multiple result groups share a heatmap cell. Narrow the display filters.")
    result = data.pivot(index=row, columns=column, values=value)
    return result.reindex(columns=columns) if columns is not None else result
