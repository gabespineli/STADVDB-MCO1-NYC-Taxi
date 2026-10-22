# React dashboard — first pass

A separate React + TypeScript + Vite application using Plotly and the seven
completed query exports. The Streamlit app stays available at its existing path.

## Run

Use Node.js 22.18+ (your installed Node 24 works) and the project's existing
Python environment. From PowerShell:

```powershell
cd C:\Users\Gab\Documents\GitHub\STADVDB-MCO1-NYC-Taxi\dashboard-react
npm install
npm run dev
```

Open **http://127.0.0.1:5173/**. Stop with **Ctrl+C**. Subsequent runs only need
`npm run dev`. Port 5173 is fixed; stop any other process using it first.

The startup command prepares the saved data automatically. If Python reports a
missing package, install the existing repository requirements:

```powershell
python -m pip install -r ..\requirements.txt
npm run dev
```

No database server or credentials are required. The app reads completed
TSV/SUCCESS-log pairs from `../dashboard/exports/`. Missing or invalid reports
show an unavailable state. It never substitutes sample data or executes SQL.

## Refresh and build

After adding completed exports, run this in a second terminal and reload:

```powershell
npm run data
```

To produce and preview a static build:

```powershell
npm run build
npm run preview
```

Preview opens at **http://127.0.0.1:4173/**. The generated `dist/` directory is
self-contained, including snapshots, the Plotly browser library, original
aggregate exports, and map boundaries. Generated assets and dependencies are
ignored by Git; recreate them with `npm run data` or `npm run build`.

## Design direction

This implements the direction established by the competitive analysis:

- A compact overview puts a monthly trajectory beside borough concentration,
  then payment composition beside rush-hour comparisons. Three separately
  scoped topline values support those charts.
- Top navigation exposes Demand, Payments, and Travel. It retracts on downward
  scroll and returns on upward scroll or keyboard focus. Mobile uses a labeled
  Queries dropdown; report links stay in a compact horizontal row.
- Controls sit beside the evidence they affect. The single Data button opens
  definitions, provenance, the current table, CSV, and the original TSV.
- Navy, taxi yellow, and restrained supporting colors encode the data.
  Findings stay short and calculated from the displayed population.
- Geographic demand uses official local taxi-zone boundaries. Hover details,
  monthly heatmaps, hourly comparisons, and paired travel-time markers provide
  the detail previously carried by long descriptions.

## Coverage and measurement rules

| View | Evidence |
| --- | --- |
| Overview | Monthly late-night demand, borough concentration, fare-tier payment mix, scoped travel-time comparison |
| Q1 · Zones & boroughs | Top 12 selected zones, official map, overlapping borough demand categories |
| Q1 · Hourly patterns | Weekday/weekend daily averages by hour; borough selector defaults to Manhattan |
| Q1 · Monthly consistency | Total monthly volume, top-three zone profiles, top-12 zone/month heatmap |
| Q2 · Fare ranges | Count/share composition by fare tier; returned mean recorded tip |
| Q2 · Borough & time | Count/share distribution for a selected period; credit-card share across boroughs and periods |
| Q3 · Rush hour & off-peak | Paired reported means for the selected distance; differences across all distance tiers |
| Q3 · Location profiles | One borough/zone identity's hourly speed, duration, or count; supporting volume heatmap |

Counts across reports have overlapping scopes. They are never combined into a
single total. Subtotals are excluded from charts. Missing periods stay gaps,
negative rush-hour differences remain visible, and zero denominators stay
unknown. Exported subgroup means are never averaged together. Hourly borough
charts use individual vertical scales, explicitly labeled on that page.

Borough/zone filters constrain the current Data table and CSV. A chart's local
period, measure, distance, or ranking can show a subset of that table; adjacent
comparisons retain their labeled broader scope. The original TSV always retains
the complete output and rollups. CSV preserves `\N` and literal `N/A`, and
prefixes spreadsheet formula-like string labels with an apostrophe.

The map joins official IDs conservatively. Ambiguous/unmatched groups remain
in totals and downloads. Shading shows pickups per zone, not geographic density.

## Validation

```powershell
npm run check
npm test
npm run build
```

On 22 October 2026:

- TypeScript and the Vite production build passed.
- Seven calculation checks passed: rollup exclusion, honest missing periods,
  payment denominators, negative differences, duplicate-cell refusal, CSV
  semantics, and reconciliation against the actual prepared exports.
- React server rendering passed for the overview, all seven report views, and
  all seven source inspectors using actual exports. Overview values reconciled
  to 23.4M weekend/late-night pickups and 67.5% card share in positive-fare trips.
- The Vite development server started on port 5173.
- Browser interaction, screenshots, mobile layout, and WebGL map rendering
  remain unverified: browser-control tools were unavailable and this session
  forbids local client socket connections. Server rendering does not verify
  Plotly's browser rendering.
- Registry DNS was blocked during authoring. Build dependencies were provisioned
  from existing local installations with matching package versions. The lockfile
  retains their original registry URLs and integrity hashes; `npm ci --dry-run`
  accepted it. A fresh registry install was not exercised in this session.

## Code

`scripts/prepare_data.py` reuses the existing validated export reader, source
definitions, and map matching; it only writes `public/data/`. It also copies the
Plotly browser runtime from the installed Python package, avoiding a second
Plotly dependency or CDN. React components, transformations, and plots live in
`src/`; this first pass adds no application backend or new Python dependency.
