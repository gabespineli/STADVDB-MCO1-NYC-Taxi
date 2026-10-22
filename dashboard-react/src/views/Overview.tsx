import { useState } from 'react';
import Chart, { Metric, Select } from '../components/Chart';
import { compact, detail, fmt, groupedSum, monthly, number, rank, ratio, rush, sum, unique } from '../analytics';
import { bars, categoryAxis, compactAxis, farePlot, leaderNote, monthlyPlot, monthNote, pairedDuration } from '../plots';
import type { Snapshot } from '../types';

export default function Overview({ snapshot }: { snapshot: Snapshot }) {
  const reports = snapshot.reports;
  const demand = detail(reports.q1_demand.rows), fares = detail(reports.q2_fare.rows);
  const months = monthly(reports.q1_monthly.rows), comparison = rush(detail(reports.q3_comparison.rows));
  const distances = unique(comparison, 'distance_bucket');
  const [distance, setDistance] = useState(distances[0] ?? '');
  const selected = comparison.filter(row => row.distance_bucket === distance);
  const maximum = rank(comparison, 'extra', 1)[0];
  const cardShare = ratio(sum(fares, 'credit_card_trips'), sum(fares, 'total_trips'));
  const boroughs = rank(groupedSum(demand, 'borough', ['total_filtered_pickups']), 'total_filtered_pickups', 20);
  return <>
    <div className="metrics-row">
      <Metric label="Weekend / late-night pickups" value={compact(sum(demand, 'total_filtered_pickups'))} />
      <Metric label="Card share · positive fares" value={cardShare === null ? '—' : fmt(cardShare, 1)} unit={cardShare === null ? '' : '%'} />
      <Metric label="Largest weekday rush-hour gap" value={maximum ? `${number(maximum.extra)! >= 0 ? '+' : ''}${fmt(number(maximum.extra), 1)}` : '—'} unit="min" />
    </div>
    <div className="chart-grid overview-grid">
      <Chart title="Late-night demand" subtitle="Monthly pickups · all reported zones" data={monthlyPlot(months)}
        layout={{ showlegend: false, xaxis: { type: 'date', tickformat: '%b', dtick: 'M2', showgrid: false, fixedrange: true }, yaxis: compactAxis() }}
        height={310} note={monthNote(months)} />
      <Chart title="Where pickups concentrate" subtitle="Weekend or late-night pickups" data={bars(boroughs, 'borough', 'total_filtered_pickups')}
        layout={{ showlegend: false, yaxis: categoryAxis, xaxis: compactAxis(), margin: { t: 8, r: 20, b: 28, l: 90 } }} height={310}
        note={leaderNote(boroughs, 'total_filtered_pickups', 'borough')} />
      <Chart title="Payment mix by fare" subtitle="Positive-fare trips · share of each tier" data={farePlot(fares, true)}
        layout={{ barmode: 'stack', yaxis: { ...compactAxis('%'), range: [0, 100] }, xaxis: { ...categoryAxis, tickfont: { size: 10 } },
          legend: { orientation: 'h', y: 1.14, x: 0 }, margin: { t: 36, r: 16, b: 52, l: 42 } }} height={310}
        note="Cash tips are not captured in these records." />
      <Chart title="Rush-hour travel time" subtitle="Weekday group averages · minutes" data={pairedDuration(selected)}
        controls={<Select label="Distance" value={distance} options={distances} onChange={setDistance} />}
        layout={{ yaxis: categoryAxis, xaxis: compactAxis(' min'), margin: { t: 36, r: 24, b: 32, l: 90 },
          legend: { orientation: 'h', x: 0, y: 1.14 } }} height={310}
        note="Rush-hour minus off-peak duration; observed differences do not establish causation." />
    </div>
    <p className="page-note">Each view uses its own query population. Report counts overlap.</p>
    {Object.values(reports).some(report => report.status !== 'Ready') && <p role="status" className="availability-note">
      Some reports are unavailable. Open Data for source status.</p>}
  </>;
}
