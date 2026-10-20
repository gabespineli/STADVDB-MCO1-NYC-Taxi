# Dashboard integration verification

## Header query navigation - 20 October 2026

Replaced the collapsed NYC Taxi expander and section/report widgets with native
`st.navigation(position="top")`. Overview is a direct header link; Q1 Demand,
Q2 Payments, and Q3 Travel contain all seven reports with distinct URL paths.
At narrow widths, the native header drawer button is visibly labeled Queries.

- Regression: 78 tests run, 70 passed, 8 opt-in MySQL checks skipped; no failures
  (20.867 seconds), using the temporary socket-free AppTest loop described below.
- Browser review confirmed header placement alongside Deploy, Q1 dropdown
  contents, and navigation from demand to hourly results using actual exports.
- At 505px and 320px, Queries remained visible beside Deploy and opened the
  native navigation drawer. Desktop payment menus also opened with Enter.
  Temporary viewport overrides were reset after verification.
- The earlier compact-interface implementation below is retained as history.

## Compact saved-only interface - 20 October 2026, evening revision

This revision replaces the source-mode UI and sidebar. The app now opens the
latest completed saved exports only, with a native collapsed top navigation bar.
There are no warehouse, sample, load-query, or refresh-query controls.
Filters and chart settings share Adjust view; tables, downloads, provenance,
and extended definitions share Data. Brief findings are computed from the
selected result groups. Chart toolbars and repeated explanatory captions were
removed; short material measurement notes remain beside charts.

- Saved-only regression: 78 tests run, 70 passed, 8 opt-in MySQL checks skipped;
  no failures (17.142 seconds). The temporary socket-free test loop described below was used.
- All seven actual local saved exports, the Overview, and the official map
  separately rendered through AppTest. Mock assertions confirmed zero database
  status or query calls.
- Navigation, collapsed control containers, every chart option, filter resets,
  missing/invalid-export states, arithmetic, and filtered/complete CSV scope
  are covered. Synthetic fixtures now simulate saved exports in UI tests;
  removed source-mode UI tests were replaced with saved-only contracts.
- Browser visual/layout review remains unverified under the same sandbox
  socket and browser URL restrictions. AppTest is not pixel or mobile QA.

Earlier source-mode and live-layout checks below describe the previous interface.

## Dashboard comparison improvements - 20 October 2026

Implemented the Overview entry page, scoped summary metrics, hourly average/total
controls, payment percentage/count and dollar-measure controls, rush-hour
duration differences, monthly zone comparisons, hourly location profiles and
heatmaps, and the optional official taxi-zone map. Definitions, populations,
missing-data treatment, small-group context, and overlapping demand categories
are visible with the affected reports.

- Regression: **80 tests run, 72 passed, 8 opt-in MySQL checks skipped**, no
  failures; 20.786 seconds. Coverage includes arithmetic, missing/zero
  denominators, missing months/hours, unpooled means, rollup exclusions,
  source transitions, controls, reset, cache/permission guards, and download scope.
- The sandbox blocks local socket connections. AppTest used a temporary,
  test-only selector event loop without a socket wakeup pipe, plus an explicitly
  writable temporary directory. No application or installed dependency was
  changed for this test adaptation. Live networking and database tests were
  not exercised by that run.
- All seven **actual local saved exports** rendered in AppTest. The official
  map, location heatmap, and bubble view also produced Plotly figures without
  exceptions. Mock assertions confirmed these checks made no warehouse status
  calls and executed no report SQL.
- Official boundaries were downloaded through NYC Open Data's GeoJSON export
  for dataset `8meu-9t5y`, then compressed without altering geometry.
  Validation confirms 263 source features representing 260 distinct IDs;
  split parts of IDs 56 and 103 become one MultiPolygon per ID. Ambiguous lookup
  labels, unknown groups, and IDs without polygons do not multiply counts and
  remain in metrics/downloads.
- `git diff --check` passed. Analytical SQL, schema, ETL, indexes, raw importer,
  and dependency requirements are unchanged. No database writes or report
  executions were performed for these changes.
- Full browser/layout QA is **not verified**: the sandbox cannot start the
  Streamlit server's local socket loop, and browser policy rejects local-file
  previews. AppTest/Plotly-figure checks do not establish pixel layout,
  interactive map rendering, keyboard accessibility, or mobile behavior.

The earlier verification below records the prior implementation's checks and
does not substitute for browser review of these new views.

Verified on 19 October 2026. This is application integration, not SQL optimization.

| Check | Result and scope |
| --- | --- |
| Seven report registrations | PASS. Q1A–Q3B select statements 1–7 from the unchanged optimized file; each has its expected aliases, population, grain, empty bindings, fingerprint, and team-supplied runtime. |
| Student SQL and database structure | PASS. No changes to analytical SQL, indexes, raw importer, schema, or ETL. No database records or privileges were modified. |
| Test suite | PASS: 70 tests, no failures or skips, with bounded read-only MySQL tests enabled. Full run: 10.369 seconds. The final disabled-control update was followed by all 27 dashboard tests passing in 12.797 seconds. |
| Charts, tables, downloads | PASS with mocked aggregate fixtures across all seven live-report layouts. All seven actual saved exports passed Streamlit AppTest rendering with charts and tables. Q2B borough/time display filters and reset passed against the supplied data. Saved-mode checks assert that no database calls occur. Display filtering and CSV scope remain covered by the existing tests. |
| Query execution and cache | PASS: startup/navigation do not run reports; exact SQL/parameter keys reuse cached executions; request IDs distinguish fresh retrieval from cache hits; targeted refresh reexecutes; one-query lock prevents competing uncached executions. |
| Failure handling | PASS: empty results and failed reloads do not substitute sample data; timeout messages omit driver secrets; locks release on exceptions; write/admin/role/grant privileges and root are rejected for live execution. |
| Parameter controls | No bind parameters exist in the seven approved statements. No database population controls are enabled. Existing-group display filters are explicitly separate. Alternate dates, populations, and aggregation levels require student-authored SQL/bindings. |
| Actual warehouse access | MySQL connectivity and lightweight six-table checks succeeded. Existing bounded tests include real warehouse EXPLAIN only and synthetic-data comparisons, not full report scans. |
| Local browser review | PASS at a narrow ~700-pixel viewport: the live account guard, source labels, and benchmark context were visible; existing Plotly sample-preview bars and legends rendered without overlap after collapsing the sidebar. This is layout evidence, not full warehouse result verification. |
| Default port 8501 | Blocked by an existing Windows system listener (PID 4). That listener was not changed. Streamlit launched on localhost:8502 for preview; configuration and normal commands retain 8501. |
| Live account | PASS after the user updated .env: the configured login is non-root and passes the direct read-only grant check. The actual SQLAlchemy connector passed SELECT 1, all six tables have records, and all seven approved report definitions pass readiness checks. The running browser displays enabled Load/Refresh controls. No expensive report was executed for this login test; credentials were not displayed or changed. |
| Saved analytical results | Seven completed TSV/log pairs are available. Q1A and Q2B were converted from the user's CSVs without rerunning SQL; Q1B/Q1C/Q2A/Q3A/Q3B came from fresh read-only executions. Q2B has 202 total rows and 161 detail groups representing 45,306,451 trips, matching Q2A's positive-fare total. Numeric field strings and literal N/A labels were preserved during conversion. Reported Q1A/Q2B benchmark runtimes are labeled as team-supplied in metadata, not newly measured. |
| Full warehouse result rendering | All seven actual saved outputs render in AppTest; checksums, row counts, and selected cross-report totals were verified. The saved-report copy update passed 27 dashboard and 5 export tests. This does not newly establish full-data equivalence to baseline SQL. |
| ngrok / another device | CLI 3.39.9 is installed and `ngrok config check` passed. No public tunnel was opened, no token was displayed, and external-device access was not tested. A valid local config does not verify online account eligibility or tunnel behavior. Follow RUNNING.md for the presentation check. |

Run the bounded checks from Windows CMD:

```cmd
set NYC_ETL_READONLY_TESTS=1
python -m unittest discover -s tests -v
set NYC_ETL_READONLY_TESTS=
```

Before presenting: configure the reporting login, choose a free local port, provide
completed exports or deliberately populate the cache, then open the ngrok HTTPS
URL on another device. Keep the laptop awake. Tests do not establish new speedups
or full-dataset equivalence.
