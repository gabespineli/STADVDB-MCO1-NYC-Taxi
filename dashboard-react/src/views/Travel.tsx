import Chart, { Select } from '../components/Chart';
import { hourly, matrix, number, palette, rush, unique } from '../analytics';
import { categoryAxis, compactAxis, heatmap, pairedDuration } from '../plots';
import type { Report, Row } from '../types';

export default function Travel({ report, rows, allRows, measure, setMeasure }: {
  report: Report; rows: Row[]; allRows: Row[]; measure: string; setMeasure: (value: string) => void;
}) {
  if (report.id === 'q3_comparison') {
    const boroughs = unique(allRows, 'borough'), distances = unique(allRows, 'distance_bucket');
    const differences = rush(allRows);
    return <div className="chart-grid">
      <Chart title="Rush hour versus off-peak" subtitle="Reported weekday group averages · minutes" height={390} data={pairedDuration(rows)}
        layout={{ yaxis: categoryAxis, xaxis: compactAxis(' min'), margin: { t: 36, r: 24, b: 36, l: 90 } }}
        note="Each pair compares the same borough and distance tier. No subgroup means are pooled." />
      <Chart title="Additional travel time" subtitle="Rush-hour minus off-peak duration · all distance tiers" height={390}
        data={heatmap(matrix(differences, 'borough', 'distance_bucket', 'extra', boroughs, distances), distances.map(item => item.replace(/^\d\. /, '')), boroughs, 'min', true)}
        layout={{ yaxis: { ...categoryAxis, autorange: 'reversed' }, xaxis: { ...categoryAxis, tickfont: { size: 10 } }, margin: { t: 8, r: 16, b: 80, l: 90 } }}
        note="Negative values mean the reported rush-hour mean was shorter. Observed differences do not establish causation." />
    </div>;
  }
  const measureKeys: Record<string, string> = { 'Speed (mph)': 'avg_speed_mph', 'Duration (min)': 'avg_duration_minutes', 'Trip count': 'trip_count' };
  const key = measureKeys[measure], periods = unique(rows, 'time_period');
  const counts = rows.map(row => ({ ...row, period: row.time_period }));
  const flagged = rows.filter(row => number(row.avg_speed_mph) !== null && number(row.avg_speed_mph)! > 80).length;
  const small = rows.filter(row => number(row.trip_count) !== null && number(row.trip_count)! < 30).length;
  return <div className="chart-grid">
    <Chart title="Hourly travel profile" subtitle={rows[0]?.zone ? String(rows[0].zone) : 'Selected zone'} height={360}
      controls={<Select label="Measure" value={measure} options={Object.keys(measureKeys)} onChange={setMeasure} />}
      data={periods.map((period, i) => ({ type: 'scatter', mode: 'lines+markers', name: period,
        x: Array.from({ length: 24 }, (_, hour) => hour), y: hourly(rows.filter(row => row.time_period === period), key),
        line: { color: palette[i], width: 2.5 }, marker: { size: 5 }, connectgaps: false,
        hovertemplate: `%{x}:00<br>%{y:,.1f} ${measure}<extra>%{fullData.name}</extra>` }))}
      layout={{ xaxis: { ...compactAxis(), tickvals: [0, 6, 12, 18, 23] }, yaxis: compactAxis(), margin: { t: 48, r: 16, b: 32, l: 48 } }}
      note={`Missing hours remain gaps. ${small} groups have fewer than 30 trips; ${flagged} have mean speeds above 80 mph.`} />
    <Chart title="Trip volume by hour" subtitle="Counts supporting the selected zone's averages" height={360}
      data={heatmap(matrix(counts, 'period', 'hour', 'trip_count', periods, Array.from({ length: 24 }, (_, hour) => hour)),
        Array.from({ length: 24 }, (_, hour) => hour), periods, 'trips')}
      layout={{ yaxis: categoryAxis, xaxis: { ...categoryAxis, tickvals: [0, 6, 12, 18, 23] }, margin: { t: 12, r: 16, b: 40, l: 90 } }}
      note="Mean speed is the mean of individual trip speeds; it is not distance divided by mean duration." />
  </div>;
}
