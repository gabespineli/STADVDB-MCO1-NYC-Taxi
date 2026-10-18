# Saved dashboard inputs

Store completed aggregated TSV results here. Query execution is managed by the
team separately; this project does not include a separate report runner.
The original analytical statements remain in the root `olap_queries.sql`.

The dashboard expects UTF-8 tab-separated files with the original output column
names. Use `\N` for SQL NULL; literal `N/A` remains a category label.

Supported filename prefixes:

| Dashboard report | Export prefix |
| --- | --- |
| Q1 zone/borough demand | q1_zone_borough |
| Q1 hourly demand | q1_hourly |
| Q1 monthly demand | q1_monthly |
| Q2 fare/payment | q2_fare_payment |
| Q2 borough/time | q2_borough_time |
| Q3 rush/off-peak | q3_rush_offpeak |
| Q3 location efficiency | q3_midrange |

Append the export's local timestamp as `_YYYYMMDD_HHMMSS_ffffff.tsv`, for example
`q3_midrange_20261018_215558_577398.tsv`. The filename timestamp is displayed as
supplied local time; it is not proof of source freshness.

Only after a query and export finish successfully, supply a matching `.log` file
with the same filename stem and these lines, using the actual row count and time:

```text
SUCCESS
Report: q3_midrange
Rows: 5802
Elapsed seconds: 453.29
```

Those numbers describe the retained original Q3 export; use your own values for
new runs. The log records successful export, not analytical approval. Do not mark
failed, interrupted, or partial output as successful. There is a 10,000-row and
25 MB limit per aggregate export. Click Refresh saved results after copying files.

Exports and logs are ignored by Git. Keep originals or backups as needed.
