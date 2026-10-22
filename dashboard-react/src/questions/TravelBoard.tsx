import { memo, useEffect, useMemo, useState } from 'react';
import { AnswerTile, BentoChart, QuestionFrame } from '../components/Bento';
import { Select } from '../components/Chart';
import { compact, detail, fmt, group, hourly, matrix, number, palette, rank, rush, sum, unique } from '../analytics';
import { categoryAxis, compactAxis, heatmap, pairedDuration } from '../plots';
import type { Snapshot } from '../types';
import type { ViewedRows } from '../questions';

function TravelBoard({ snapshot, onViewsChange }: { snapshot: Snapshot; onViewsChange: (views: ViewedRows) => void }) {
  const data = useMemo(() => ({ comparison: detail(snapshot.reports.q3_comparison.rows), location: detail(snapshot.reports.q3_location.rows) }), [snapshot]);
  const distances = unique(data.comparison, 'distance_bucket'), boroughs = unique(data.comparison, 'borough');
  const [distance, setDistance] = useState(distances.find(value => value.startsWith('2.')) ?? distances[0] ?? '');
  const [zone, setZone] = useState(''), [measure, setMeasure] = useState('Speed (mph)');
  const zones = useMemo(() => rank([...group(data.location, ['borough', 'zone']).values()].map(rows => ({
    label: `${rows[0].zone} · ${rows[0].borough}`, trip_count: sum(rows, 'trip_count'),
  })), 'trip_count', Number.MAX_SAFE_INTEGER).map(row => String(row.label)), [data]);
  const selectedZone = zones.includes(zone) ? zone : zones[0] ?? '';
  const location = useMemo(() => data.location.filter(row => `${row.zone} · ${row.borough}` === selectedZone), [data, selectedZone]);
  const viewed = useMemo(() => ({ q3_comparison: data.comparison, q3_location: location }), [data, location]);
  useEffect(() => onViewsChange(viewed), [viewed, onViewsChange]);
  const selected = data.comparison.filter(row => row.distance_bucket === distance), differences = rush(data.comparison);
  const peak = rank(rush(selected), 'extra', 1)[0], gap = number(peak?.extra);
  const periods = unique(location, 'time_period');
  const key = { 'Speed (mph)': 'avg_speed_mph', 'Duration (min)': 'avg_duration_minutes', 'Trip count': 'trip_count' }[measure]!;
  const small = location.filter(row => number(row.trip_count) !== null && number(row.trip_count)! < 30).length;
  const flagged = location.filter(row => number(row.avg_speed_mph) !== null && number(row.avg_speed_mph)! > 80).length;
  return <QuestionFrame id="travel" snapshot={snapshot}>
    <AnswerTile label="Largest selected rush-hour gap" value={gap === null ? 'Unavailable' : `${gap >= 0 ? '+' : ''}${fmt(gap, 1)}`} unit={gap === null ? '' : 'min'}
      detail={peak ? String(peak.borough) : 'Awaiting travel results'} context={distance.replace(/^\d\. /, '')} />
    <BentoChart area="comparison" title="How much longer" subtitle="Weekday group means · minutes" height={285}
      controls={<Select label="Comparison distance" value={distance} options={distances} onChange={setDistance} />}
      data={pairedDuration(selected)} layout={{ xaxis: compactAxis(' min'), yaxis: categoryAxis, margin: { t: 32, r: 12, b: 24, l: 80 } }}
      note="Rush-hour minus off-peak; this is an observed difference, not causation." />
    <BentoChart area="differences" title="Where the gap changes" subtitle="Additional minutes · all distance tiers" height={285}
      data={heatmap(matrix(differences, 'borough', 'distance_bucket', 'extra', boroughs, distances), distances.map(value => value.replace(/^\d\. /, '')), boroughs, 'min', true)}
      layout={{ xaxis: { ...categoryAxis, tickfont: { size: 9 } }, yaxis: { ...categoryAxis, autorange: 'reversed', tickfont: { size: 10 } }, margin: { t: 0, r: 8, b: 64, l: 72 } }} />
    <AnswerTile area="coverage" label="Selected zone profile" value={compact(sum(location, 'trip_count'))} unit="trips"
      detail={location[0] ? String(location[0].zone) : 'No location groups'} context={`${small} hourly groups below 30 trips · ${flagged} above 80 mph`} />
    <BentoChart area="profile" title="How the day unfolds" subtitle="Weekday trips of 2–5 miles" height={150}
      controls={<div className="chart-controls"><Select label="Travel zone" value={selectedZone} options={zones} onChange={setZone} />
        <Select label="Profile measure" value={measure} options={['Speed (mph)', 'Duration (min)', 'Trip count']} onChange={setMeasure} /></div>}
      data={periods.map((period, index) => ({ type: 'scatter', mode: 'lines+markers', name: period,
        x: Array.from({ length: 24 }, (_, hour) => hour), y: hourly(location.filter(row => row.time_period === period), key),
        line: { color: palette[index], width: 2.5 }, marker: { size: 4 }, connectgaps: false,
        hovertemplate: `%{x}:00<br>%{y:,.1f} ${measure}<extra>%{fullData.name}</extra>` }))}
      layout={{ xaxis: { ...compactAxis(), tickvals: [0, 6, 12, 18, 23] }, yaxis: compactAxis(), margin: { t: 28, r: 8, b: 24, l: 40 } }} />
    <BentoChart area="volume" title="How much data supports it" subtitle="Selected zone · trip counts by hour" height={150}
      data={heatmap(matrix(location, 'time_period', 'hour', 'trip_count', periods, Array.from({ length: 24 }, (_, hour) => hour)),
        Array.from({ length: 24 }, (_, hour) => hour), periods, 'trips')}
      layout={{ xaxis: { ...categoryAxis, tickvals: [0, 6, 12, 18, 23] }, yaxis: { ...categoryAxis, tickfont: { size: 10 } }, margin: { t: 0, r: 8, b: 24, l: 80 } }}
      note="Missing hours remain gaps; exported means are not pooled." />
  </QuestionFrame>;
}

export default memo(TravelBoard);
