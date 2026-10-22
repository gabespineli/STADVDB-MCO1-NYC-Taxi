# React dashboard — question-led bento

React + TypeScript + Vite + Plotly, using the seven completed query exports.
The Streamlit application remains available at its existing path.

## Run

Use Node.js 22.18+ and the project's existing Python environment:

```powershell
cd C:\Users\Gab\Documents\GitHub\STADVDB-MCO1-NYC-Taxi\dashboard-react
npm install
npm run dev
```

Open **http://127.0.0.1:5173/**. Stop with **Ctrl+C**. Subsequent runs only need
`npm run dev`. Startup prepares the saved results automatically. If Python
reports a missing package, install the existing requirements:

```powershell
python -m pip install -r ..\requirements.txt
```

## One question, one bento

All three questions appear on one continuous page. Header links jump to a
question; there are no separate overview/report tabs. The layout uses unequal
tiles to distinguish the leading answer, primary comparison, and supporting
evidence. Mobile stacks the same evidence. Local selections survive navigation
between questions. Earlier `#/q1_*`, `#/q2_*`, and `#/q3_*` links resolve to their
question.

Card backgrounds group related evidence: yellow for text-heavy answers and
coverage context, blue for geographic/category comparisons, green for temporal
patterns, and warm cream for fare/tip details. Chart labels use darker secondary
text, and the amber series stays dark enough to stand apart from tinted cards.

Yellow cards now summarize computed patterns: leading zone with temporal peaks,
the lowest/highest fare-tier card shares, and rush-hour differences against the
off-peak baseline. They update with compatible selections.

- **Demand:** select a ranking bar, map zone, or zone dropdown. The map/ranking
  highlight that zone, the hourly chart changes to its borough, and the monthly
  trend follows its zone name only when the name identifies one borough/zone.
  Ambiguous names retain the all-zone trend with an explicit note. Select
  **All zones** to clear; changing the hourly borough also clears zone focus.
- **Payments:** fare bars and recorded tips share one fare selection. The card
  heatmap and borough distribution share borough/time focus. Those two groups
  stay independent because the exports do not contain their joint dimensions.
  The dropdowns provide keyboard selection and **All** options clear focus.
- **Travel:** select paired dots, a difference cell, or a borough dropdown to
  coordinate the comparison and the available zone profiles. Difference cells
  also set comparison distance. Profiles retain their labeled weekday 2–5-mile
  scope; their distance population does not change with the comparison tier.

Share axes and heatmaps always span 0–100%. Duration-difference heatmaps have
equal positive/negative limits around zero. Category colors stay stable when
methods or periods disappear. Share hovers include the exact numerator and
denominator; profile-average hovers include their own group trip counts.

| Question | Evidence kept together |
| --- | --- |
| Q1 · Where and when is taxi demand strongest? | Leading zone and share, geographic demand, zone ranking, weekday/weekend hourly profiles, monthly volume, and zone/month consistency |
| Q2 · How do payments vary by fare, place, and time? | Card share, fare-tier composition, recorded tips, credit-card heatmap, and borough/payment comparisons |
| Q3 · Where does rush-hour travel take longer? | Selected duration difference, paired means, distance/borough differences, selected-zone hourly profile, trip-volume support, and small/extreme-group context |

The single **Data** button follows the question currently in view. Its report
selector contains that question's supporting queries. All seven source tables,
definitions, provenance, CSV downloads, and original TSV downloads remain
available. The navbar retracts on downward scroll and returns on upward scroll
or keyboard focus.

## Data and scopes

The app reads validated TSV/SUCCESS-log pairs from `../dashboard/exports/`.
No database connection is needed. It never executes queries or substitutes
samples. `scripts/prepare_data.py` reuses the existing readers, definitions,
and conservative official taxi-zone matching, and copies the installed Python
Plotly browser library locally. No CDN or new Python dependency is needed.

- Demand map/rankings cover weekends **or** late night. Monthly views cover
  late night; hourly views compare represented weekday/weekend dates in their
  selected borough. Those are supporting comparisons with separately labeled
  populations, not one joined dataset.
- Payment shares use their own fare-tier or borough/time denominators. Cash
  tips are not captured; returned recorded-tip means are not pooled.
- Rush-hour comparisons use their labeled distance tier. Location profiles
  retain their fixed weekday 2–5-mile scope and exact borough/zone identity.
  Negative gaps remain visible. Observed differences are not causal evidence.
- Missing periods remain gaps. Subtotals are excluded from plots. Unknown
  denominators stay unknown, and exported group means are never averaged.
- Data/CSV reflect the selected hourly borough, compatible monthly zone,
  payment borough/time, or location profile. Other
  chart-local selections and top-N rankings can show subsets of their source
  table. The complete original TSV always preserves rollups and SQL `\N`.
- CSV preserves nulls and literal `N/A`; formula-like string labels receive a
  leading apostrophe for spreadsheet safety. Counts across reports overlap.
- Map shading is pickups per zone, not area density. Ambiguous/unmatched
  labels remain in source tables and totals.

## Refresh and build

After adding completed exports, run `npm run data` in a second terminal and
reload. To generate and preview a static build:

```powershell
npm run build
npm run preview
```

Preview runs on **http://127.0.0.1:4173/**. The generated `dist/` includes the
snapshots, Plotly runtime, original aggregate exports, and map boundaries.
Generated data, build output, and dependencies are ignored by Git.

## Verification — 22 October 2026

`npm run build` and all twelve `npm test` checks passed. React server
rendering verified each combined question, all seven source choices, and legacy
query-link routing. The model checks cover rollups, missing periods, local
payment denominators, negative gaps, duplicate-cell refusal, CSV handling, and
reconciliation against actual saved exports, safe zone coordination, selection
identities, fixed percentage/diverging scales, stable colors, and hover evidence.

Browser interaction, screenshots, responsive layout, and WebGL rendering remain
unverified because browser-control tools are unavailable in this session.
Server rendering does not verify Plotly's browser rendering. The reference text
attachment returned no extracted text and its download failed; this revision
implements the user's question-led bento request without claiming to reproduce
that attachment.

During initial setup, registry DNS was blocked. Matching dependencies were
provisioned from existing local installations; original registry/integrity
metadata was retained in the lockfile, and `npm ci --dry-run` accepted it.
A fresh registry install was not exercised in this session.
