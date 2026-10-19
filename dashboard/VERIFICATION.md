# Dashboard integration verification

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
