# Student-authored reporting SQL

No analytical SQL is generated here. The dashboard does not execute the root
`olap_queries.sql` automatically. Its seven statements define these result contracts:

| Statement in `olap_queries.sql` | Report ID / file to supply |
| --- | --- |
| Q1 zone/borough demand | `q1_demand` / `q1_demand.sql` |
| Q1 hourly demand | `q1_hourly` / `q1_hourly.sql` |
| Q1 monthly consistency | `q1_monthly` / `q1_monthly.sql` |
| Q2 fare ranges | `q2_fare` / `q2_fare.sql` |
| Q2 payment distribution | `q2_payment` / `q2_payment.sql` |
| Q3 rush/off-peak comparison | `q3_comparison` / `q3_comparison.sql` |
| Q3 location efficiency | `q3_location` / `q3_location.sql` |

## Connect a finalized statement

1. The OLAP teammate validates the SQL and its population, dimensions, numeric
   handling, grouping, and expected result size independently.
2. Put that **one complete statement**, unchanged, in the corresponding file above.
   Keep the output aliases listed in `dashboard/reports.py`. Use unqualified
   warehouse table names; the dashboard selects its configured reporting database.
   SELECT/WITH statements, explicit JOINs, and local CTEs are supported. Comma
   joins are refused by the conservative guard. Source/raw tables,
   cross-database references, executable MySQL comments, exports, locking, and
   multiple statements are refused. There is no runtime SQL editor or file upload.
3. In `dashboard/reports.json`, document `population` and `grain`. Set `aggregated`
   and `validated` to JSON `true` only after the team accepts the query. Validation
   is a team sign-off, not a claim that table existence proves correct ETL.
4. Add only validated filters to that report's `filters` mapping. Values are the
   teammate's SQLAlchemy-style named bind parameters, without the leading colon.
   An example mapping is `{"borough": "borough_parameter"}`. The student-authored
   SQL must already implement the corresponding `:borough_parameter` predicate.
   The application does not append predicates, wrap the statement, add LIMIT, or
   optimize it. All statement parameters must have matching filter bindings.
5. Select **Warehouse reports**, choose the report, and click **Load warehouse
   report**. Compare its detailed result and CSV with the teammate's independently
   verified result, including NULLs and rollup rows.

## Filter contract

| UI control key | Bound Python value |
| --- | --- |
| `borough`, `zone`, `time_period` | Selected string; `None` for All |
| `month` | Integer 1–12; `None` for All |
| `start_date`, `end_date` | Python dates; declare both; UI dates cover 2025 |
| `fare_min`, `fare_max` | Numbers; both `None` unless Limit fare range is checked; declare both |
| `distance_category` | Existing distance-bucket label from `sample_data.DISTANCES`; `None` for All |
| `aggregation` | `Zone` or `Borough` |

The teammate must explicitly validate NULL/All handling, inclusive/exclusive date
boundaries, enum labels, and each enabled aggregation level. Any selectable level
must maintain the report's result contract. Do not enable a control merely because
its parameter name is present. Filtering occurs in the approved SQL, not by
discarding rows or averaging subgroup results in pandas.

## Result/display contract

- Required output aliases and numeric fields live in `dashboard/reports.py`.
- Result retrieval accepts at most 10,000 aggregated rows. Larger results are
  rejected rather than silently truncated. This is a client memory safeguard,
  not a SQL execution optimization or a server-side row limit.
- Original rollup rows remain in detailed tables and downloads. Charts omit the
  existing total/subtotal labels and sum only additive count measures where needed.
  Keep those labels compatible, or have the UI teammate update `ROLLUP_LABELS`
  in `charts.py` when the approved query contract changes.
- Means are shown at their returned grain, never summed or averaged across groups.
  NULL metrics are not replaced with zeros. Missing columns or nonnumeric measures
  produce a clear integration error.
- A zero-row live result stays empty. A failed live report never falls back to
  synthetic samples. The fetched timestamp, applied parameters, and classification
  remain visible, and CSV exports identify sample versus warehouse data.
- Availability checks flag missing time classifications and generated `Zone <ID>`
  labels. They do not certify FK completeness, date coverage, or full data quality.
