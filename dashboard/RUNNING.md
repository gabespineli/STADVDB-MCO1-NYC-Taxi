# Run the saved-results dashboard

From the repository directory:

```powershell
python -m streamlit run dashboard/app.py --server.port 8502
```

Port 8501 may already be used by a Windows system listener. Use the same port
when opening the dashboard or starting an ngrok tunnel.

## Browse the data

The dashboard reads completed exports from `dashboard/exports/` only. MySQL is
not required to view results. There is no source selector or sample mode.

- Navigation lives in Streamlit's header alongside Deploy. **Overview** opens
  the summary; **Q1 · Demand**, **Q2 · Payments**, and **Q3 · Travel** open
  menus containing the seven reports. On narrow screens, **Queries** in the
  header opens the native navigation drawer.
- **Adjust view** contains filters, chart settings, and Reset view.
- **Data** contains the filtered table, CSV download, scope and methodology.
  Source and complete output retains the full original export and rollups.
- Overview shows separate demand, payment-share, and duration-gap summaries.
  Its reports have overlapping populations; their trip totals are not additive.

Charts lead each page. Brief findings are calculated from the selected groups;
short measurement notes remain next to affected visuals. Detailed definitions
are available in Data. Missing periods remain gaps and subgroup means are never
averaged together.

## Add completed results

Copy each final timestamped TSV and matching SUCCESS log into
`dashboard/exports/`, following [exports/README.md](exports/README.md).
The latest completed run opens automatically. New files are discovered on each
rerun; reload the page after copying results. Cached file reads include the
export's size, modification time, and completion metadata in their identity.

Failed, partial, mismatched, or missing exports never fall back to samples or
database queries. Filters select existing aggregate groups only. Chart-specific
rankings and zone selections do not narrow the filtered-table download.
SQL NULL remains `\\N`; literal `N/A` remains a label.

## Map

Enable Taxi-zone map under Adjust view on Zone and borough demand.
The bundled boundaries come from official NYC Open Data dataset `8meu-9t5y`;
the source and checksum are recorded in `reference_data/taxi_zones.source.json`.
The 263 source features represent 260 distinct IDs. Split polygon parts are
combined by ID without changing coordinates. Ambiguous labels and IDs without
boundaries remain in totals and downloads. Shading represents pickups per zone,
not density per unit area. No map token or external tile service is needed.

## Share locally with ngrok

Leave Streamlit running and, after configuring ngrok locally, run:

```powershell
ngrok http 8502
```

Share the HTTPS forwarding address and stop the tunnel after the presentation.
Visitors can browse saved results and download aggregates; no database query
controls are exposed. Keep Streamlit, ngrok, and the computer awake.

Analytical SQL, importer, ETL, schema, indexes, and dependency requirements are
unchanged. Database query utilities remain separate from the dashboard.
See [VERIFICATION.md](VERIFICATION.md) for checks and limitations.
