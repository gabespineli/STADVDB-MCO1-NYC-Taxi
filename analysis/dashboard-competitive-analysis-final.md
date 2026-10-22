# Final dashboard competitive analysis

Reviewed 22 October 2026. Target: the React dashboard in `dashboard-react/`,
covering the seven saved 2025 yellow-taxi query exports.

## Recommendation

Retain the continuous, question-led bento layout and its yellow answer cards.
The next iteration should make the evidence behave coherently, turn headline
values into concise findings, and improve comparison readability. Another
framework change or a larger collection of cards would contribute less to the
three questions this application needs to answer.

This is a source-backed competitive review and code inspection. Public pages,
their published descriptions, and the local React implementation were inspected;
competitor interactions and local browser layout were not exercised. No user
study, visual usability score, or measured performance comparison is claimed.
Recommendations below are judgments based on that evidence.

## Relevant benchmarks

| Reference | Observed pattern | Application to this dashboard | Scope limit |
| --- | --- | --- | --- |
| NYC TLC Factbook | TLC documents current snapshots alongside historical metrics, precise hover values, category isolation, a glossary, and interactive zone maps. | Combine an answer with its comparison; retain compact source definitions and geographic inspection. | The official walkthrough describes its published design; this review did not operate the current Power BI app. Its broader industry scope is different from our 2025 yellow-taxi exports. |
| Todd Schneider's NYC taxi and ridehailing dashboard | A focused monthly comparison with category selection and explicit notes about sources, update lag, omissions, and underlying data access. | Prioritize a meaningful comparison; make period and source context easy to inspect. | JavaScript chart interaction was not tested. Its service-class comparisons are not measurements available in our exports. |
| Emily Cheng's City in Motion | Three stated questions organize market share, temporal patterns, and geography. The page documents year selection, vehicle filters, hour/day heatmaps, and zone exploration. | Keep the question-led organization and make exploration meaningful across compatible views. | Borrow its organization and interaction ideas, not its numerical findings, policy interpretations, long commentary, or unavailable dimensions. |
| QuestDB's NYC taxi/Grafana showcase | Historical 2015 replay with compact metrics, temporal comparisons, and inspectable SQL behind panels. | Keep supporting methods out of the reading path while preserving inspection. | Historical replay is explicitly different from live taxi telemetry and from our saved 2025 snapshots. No real-time claim is appropriate for this project. |

Grafana's guidance emphasizes answering a question and reducing cognitive
load. Tableau's guidance supports coordinated views, discoverable interactions,
purposeful chart selection, device-aware layouts, and consistent use of color.
These support the current direction; they do not establish that every chart
should be visible at the same size or respond to every filter.

## What the current implementation establishes

- All three questions are on one page, with navigation anchors rather than
  report subtabs. Each question retains its supporting queries in Data.
- Yellow answer/context cards contrast with blue comparison, green temporal,
  and cream fare/tip surfaces. This is a useful grouping convention to retain.
- Demand includes a zone ranking, official map, hourly comparison, monthly
  trend, and monthly zone matrix. Payments includes share comparisons and
  recorded tips. Travel includes paired means, signed differences, a location
  profile, and its supporting volume.
- Subtotal exclusion, missing-period gaps, local payment denominators, and
  refusal to pool ambiguous exported means are already implemented.
- The remaining gap is behavioral and interpretive: adjacency does not yet
  mean that the cards share an investigation or provide a complete answer.

## Findings from the current code

### 1. Yellow cards summarize values better than they answer their questions

Demand names a leading zone but does not summarize the hourly or monthly
pattern. Payments shows an overall credit-card share while the question asks
how payment differs. Travel's selected maximum gap is closer to an answer,
but it cannot communicate the strength of its supporting sample.

An actual saved-export example illustrates the opportunity: credit-card share
is 73.4% below $10, 67.3% at $10–24.99, 55.7% at $25–49.99, and 75.6% at $50+.
The overall 67.5% card share conceals this non-monotonic pattern. A short finding
about the middle-tier dip and high-tier rebound answers more of Q2 than the
overall share alone. This is descriptive and does not imply a causal effect
of fare on payment choice.

### 2. The cards use separate contexts

Demand's hourly chart initially selects Manhattan, while the map/ranking use
all reported weekend-or-late-night groups and monthly views use all reported
late-night zones. Travel's comparison defaults to a distance tier, while its
profile defaults to the highest-volume borough/zone identity. Those are valid
individual views, but users must mentally connect them.

`Chart.tsx` has a click callback mechanism, but the question boards do not use
it to connect marks. The map also lacks a selected-zone identity callback.

### 3. The consistency heatmap currently encodes size

The monthly matrix displays absolute counts for five high-volume zones.
It helps identify busy zones and months, but a large zone can remain dark
throughout the year while masking meaningful changes within that zone.
The current title should not be read as a formal stability measurement.

### 4. Scale and tooltip context can be stronger

The credit-card heatmap does not explicitly fix its color range at 0–100%.
Payment-share tooltips primarily show percentages; adding the underlying count
and denominator would distinguish common patterns from small-group extremes.
Recurring categories should retain explicit colors across selections.

### 5. Concision has pushed some labels very small

Bento helper text is 10px and some axes are configured at 9px. The CSS stacks
the complete card collection on mobile. Without browser review, clipping and
touch behavior remain unknown. There is a concrete reason to inspect those
sizes, rather than assuming that a successful build verifies readability.

## Ordered implementation recommendations

| Order | Change | Acceptance condition | Existing exports sufficient? |
| --- | --- | --- | --- |
| 1 | Turn each yellow card into one short, computed finding plus its key number. | Q1 summarizes location and a labeled temporal pattern; Q2 expresses a difference across groups; Q3 states the selected duration difference. Findings update with their applicable selections and identify their population. | Yes, within available grains. |
| 2 | Introduce coordinated selections inside each question. | A zone/bar click highlights the matching map zone; compatible monthly views follow that exact zone; the hourly panel follows its borough with that scope stated. A travel comparison borough directs profile choices to that borough. The same selections are keyboard accessible and clearable. | Partly: use only the mapping rules below. |
| 3 | Make temporal consistency comparable within a zone. | A pattern view indexes each zone against its own typical month, with a plain label such as “Typical month = 100.” Retain absolute counts in hover/source inspection; preserve unknown months and disclose incomplete coverage. | Yes for a relative monthly-count pattern. A full-year baseline requires all 12 observed months. This does not remove the effect of month length. |
| 4 | Standardize analytical scales, category colors, and hover evidence. | Credit-card share always uses 0–100%; duration differences retain a zero-centered diverging scale; payment and period categories keep their colors; share tooltips include numerator and denominator. | Yes. |
| 5 | Adjust hierarchy and readable sizing after rendered review. | Inspect 320, 768, 1024, and 1440px layouts. Target at least 12px chart/helper text and readable controls; grow or simplify a panel before shrinking text. On mobile, order answer, primary comparison, then supporting evidence. Fold Q3's separate count tile into profile context if it frees useful plotting space. | Yes. |
| 6 | Improve evidence-strength treatment for travel. | Show counts beside the profile averages already backed by `trip_count`; visibly distinguish small groups. Add rush/off-peak comparison counts before presenting those differences as well-supported rankings. | Profile counts: yes. Rush/off-peak comparison counts: new approved output required. |

Recommended first implementation batch: 1, the safe portions of 2, and 4.
Then refine the consistency view and inspect the rendered layouts. Treat new
comparison-count exports as a separate data enhancement, not a UI prerequisite.

## Selection boundaries that must remain honest

- Q1 hourly rows have borough and hour, not taxi zone. Selecting JFK cannot
  produce a JFK hourly curve from those exports. The compatible hourly view
  is Queens, explicitly labeled as borough-level context.
- Q1 monthly rows identify a zone by label and omit borough/official ID.
  Connect them to the map only when that identity is unambiguous; do not infer
  a borough match for ambiguous names.
- Demand's map/ranking cover weekends OR late night; its monthly series covers
  late night. Coordinated highlighting does not make those populations equal.
- Q2's fare-tier export does not contain borough/time, and its borough/time
  export does not contain fare tier. A fare selection cannot filter the latter
  without a new export. Connect selections within compatible views only.
- Q3's location profile is fixed to weekday 2–5-mile trips. Changing the
  comparison distance must not imply that this profile changed its distance
  population. Keep its scope visible.
- Q3 comparison rows have no trip counts. Counts from the location profile
  cannot validate the sample size of a different comparison population.

## Bound the final iteration

Keep the existing framework, saved-export source, three questions, compact
navigation, and yellow answer convention. Additional dates, day-of-week heatmaps,
hour-by-zone animation, cross-service market share, causal explanations, and
cross-filtering across absent dimensions require additional evidence. They
should not be introduced as cosmetic improvements to this dashboard.

No application changes were made for this review.

## Inspected local evidence

- [Question definitions](../dashboard-react/src/questions.ts)
- [Demand board](../dashboard-react/src/questions/DemandBoard.tsx)
- [Payments board](../dashboard-react/src/questions/PaymentsBoard.tsx)
- [Travel board](../dashboard-react/src/questions/TravelBoard.tsx)
- [Chart interaction wrapper](../dashboard-react/src/components/Chart.tsx)
- [Map](../dashboard-react/src/components/ZoneMap.tsx)
- [Color scales and plot builders](../dashboard-react/src/plots.ts)
- [Source inspection](../dashboard-react/src/components/DataDialog.tsx)
- [Layout and color rules](../dashboard-react/src/bento.css)
- [Approved result contracts](../dashboard/reports.py)

Actual prepared exports were read to confirm result grains and the Q2 example.
Their values are project observations, not statistics taken from competitors.

## Public sources

Accessed 22 October 2026:

1. [NYC TLC Data and Reports](https://www.nyc.gov/site/tlc/about/data-and-research.page)
2. [TLC's published Factbook walkthrough](https://medium.com/@NYCTLC/introducing-the-tlc-factbook-nyc-tlcs-new-data-dashboard-4eec7f9c5e4c), 13 November 2023
3. [Todd Schneider — NYC Taxi & Ridehailing Stats](https://toddwschneider.com/dashboards/nyc-taxi-ridehailing-uber-lyft-data/)
4. [Emily Cheng — City in Motion](https://emilycheng156.github.io/nyc-taxi-mobility-analysis/)
5. [QuestDB — NYC Taxi Data showcase](https://questdb.com/dashboards/taxi/)
6. [Grafana — Dashboard best practices](https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/best-practices/)
7. [Tableau — Visual best practices](https://help.tableau.com/current/blueprint/en-us/bp_visual_best_practices.htm)
