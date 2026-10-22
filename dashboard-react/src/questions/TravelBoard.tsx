import { memo, useEffect, useMemo, useState } from 'react';
import { AnswerTile, BentoChart, QuestionFrame } from '../components/Bento';
import { Select } from '../components/Chart';
import { categoryColor, compact, detail, fmt, group, hourly, matrix, maximum, number, rank, rush, sum, unique, zoneId, zoneLabel } from '../analytics';
import { categoryAxis, compactAxis, focusCell, heatmap, pairedDuration } from '../plots';
import type { Snapshot } from '../types';
import type { ViewedRows } from '../questions';

function TravelBoard({ snapshot, onViewsChange }: { snapshot: Snapshot; onViewsChange: (views: ViewedRows) => void }) {
  const data = useMemo(() => ({ comparison: detail(snapshot.reports.q3_comparison.rows), location: detail(snapshot.reports.q3_location.rows) }), [snapshot]);
  const distances = unique(data.comparison, 'distance_bucket'), boroughs = unique(data.comparison, 'borough');
  const [distance, setDistance] = useState(distances.find(value => value.startsWith('2.')) ?? distances[0] ?? '');
  const [zone, setZone] = useState(''), [measure, setMeasure] = useState('Speed (mph)');
  const [borough, setBorough] = useState('');
  const zones = useMemo(() => rank([...group(data.location, ['borough', 'zone']).values()].map(rows => ({
    id: zoneId(rows[0]), label: zoneLabel(rows[0]), borough: rows[0].borough, trip_count: sum(rows, 'trip_count'),
  })), 'trip_count', Number.MAX_SAFE_INTEGER), [data]);
  const eligibleZones = zones.filter(row => !borough || row.borough === borough);
  const selectedZone = eligibleZones.some(row => row.id === zone) ? zone : String(eligibleZones[0]?.id ?? '');
  const location = useMemo(() => data.location.filter(row => zoneId(row) === selectedZone), [data, selectedZone]);
  const viewed = useMemo(() => ({ q3_comparison: data.comparison, q3_location: location }), [data, location]);
  useEffect(() => onViewsChange(viewed), [viewed, onViewsChange]);
  const selected = data.comparison.filter(row => row.distance_bucket === distance), differences = rush(data.comparison);
  const peak = borough ? rush(selected).find(row => row.borough === borough) : rank(rush(selected), 'extra', 1)[0], gap = number(peak?.extra);
  const distanceLabels = distances.map(value => value.replace(/^\d\. /, ''));
  const selectCell = (value: string) => {
    try { const [b, d] = JSON.parse(value); if (boroughs.includes(b) && distances.includes(d)) { setBorough(b); setDistance(d); } } catch { /* Ignore non-data plot clicks. */ }
  };
  const differencePlot = heatmap(matrix(differences, 'borough', 'distance_bucket', 'extra', boroughs, distances), distanceLabels, boroughs, 'min', true, maximum(differences, 'extra')).map(trace => ({ ...trace,
    customdata: boroughs.map(b => distances.map(d => { const row = differences.find(item => item.borough === b && item.distance_bucket === d); return [JSON.stringify([b, d]), number(row?.off_peak_duration_min), number(row?.rush_hour_duration_min)]; })),
    hovertemplate: '%{y} · %{x}<br>Off-peak: %{customdata[1]:.1f} min<br>Rush: %{customdata[2]:.1f} min<br>Difference: %{z:.1f} min<extra></extra>' }));
  const periods = unique(location, 'time_period');
  const key = { 'Speed (mph)': 'avg_speed_mph', 'Duration (min)': 'avg_duration_minutes', 'Trip count': 'trip_count' }[measure]!;
  const small = location.filter(row => number(row.trip_count) !== null && number(row.trip_count)! < 30).length;
  const flagged = location.filter(row => number(row.avg_speed_mph) !== null && number(row.avg_speed_mph)! > 80).length;
  return <QuestionFrame id="travel" snapshot={snapshot}>
    <AnswerTile label={borough ? 'Selected rush-hour difference' : 'Largest selected rush-hour difference'} value={gap === null ? 'Unavailable' : `${gap >= 0 ? '+' : ''}${fmt(gap, 1)}`} unit={gap === null ? '' : 'min'}
      detail={peak ? `${peak.borough} · ${distance.replace(/^\d\. /, '')}` : 'Awaiting travel results'}
      context={peak ? `${fmt(number(peak.off_peak_duration_min), 1)} → ${fmt(number(peak.rush_hour_duration_min), 1)} min${number(peak.percent) === null ? '' : ` · ${number(peak.percent)! >= 0 ? '+' : ''}${fmt(number(peak.percent), 1)}% vs off-peak`}` : undefined} />
    <BentoChart area="comparison" title="How much longer" subtitle="Weekday group means · minutes" height={285}
      controls={<div className="chart-controls"><Select label="Travel borough" value={borough} options={[{ value: '', label: 'All boroughs' }, ...boroughs]} onChange={setBorough} />
        <Select label="Comparison distance" value={distance} options={distances} onChange={setDistance} /></div>}
      onSelect={setBorough} data={pairedDuration(selected, borough)} layout={{ xaxis: { ...compactAxis(' min'), range: [0, Math.max(maximum(data.comparison, 'off_peak_duration_min'), maximum(data.comparison, 'rush_hour_duration_min')) * 1.05] }, yaxis: categoryAxis, margin: { t: 32, r: 12, b: 24, l: 80 } }}
      note="Rush-hour minus off-peak; this is an observed difference, not causation." />
    <BentoChart area="differences" title="Where the gap changes" subtitle="Additional minutes · all distance tiers" height={285}
      onSelect={selectCell} data={[...differencePlot, ...focusCell(distance.replace(/^\d\. /, ''), borough)]}
      layout={{ xaxis: { ...categoryAxis, tickfont: { size: 9 } }, yaxis: { ...categoryAxis, autorange: 'reversed', tickfont: { size: 10 } }, margin: { t: 0, r: 8, b: 64, l: 72 } }} />
    <AnswerTile area="coverage" label="Selected zone profile" value={compact(sum(location, 'trip_count'))} unit="trips"
      detail={location[0] ? String(location[0].zone) : 'No location groups'} context={`${small} hourly groups below 30 trips · ${flagged} above 80 mph`} />
    <BentoChart area="profile" title="How the day unfolds" subtitle="Weekday trips of 2–5 miles" height={150}
      controls={<div className="chart-controls"><Select label="Travel zone" value={selectedZone} options={eligibleZones.map(row => ({ value: String(row.id), label: String(row.label) }))} onChange={value => { setZone(value); const row = zones.find(row => row.id === value); if (row) setBorough(String(row.borough)); }} />
        <Select label="Profile measure" value={measure} options={['Speed (mph)', 'Duration (min)', 'Trip count']} onChange={setMeasure} /></div>}
      data={periods.map(period => ({ type: 'scatter', mode: 'lines+markers', name: period,
        x: Array.from({ length: 24 }, (_, hour) => hour), y: hourly(location.filter(row => row.time_period === period), key),
        customdata: hourly(location.filter(row => row.time_period === period), 'trip_count'),
        line: { color: categoryColor(period), width: 2.5 }, marker: { size: 4 }, connectgaps: false,
        hovertemplate: `%{x}:00<br>%{y:,.1f} ${measure}<br>%{customdata:,} trips in this group<extra>%{fullData.name}</extra>` }))}
      layout={{ xaxis: { ...compactAxis(), tickvals: [0, 6, 12, 18, 23], range: [0, 23] }, yaxis: { ...compactAxis(), rangemode: 'tozero' }, margin: { t: 28, r: 8, b: 24, l: 40 } }} />
    <BentoChart area="volume" title="How much data supports it" subtitle="Selected zone · trip counts by hour" height={150}
      data={heatmap(matrix(location, 'time_period', 'hour', 'trip_count', periods, Array.from({ length: 24 }, (_, hour) => hour)),
        Array.from({ length: 24 }, (_, hour) => hour), periods, 'trips', false, maximum(data.location, 'trip_count'))}
      layout={{ xaxis: { ...categoryAxis, tickvals: [0, 6, 12, 18, 23] }, yaxis: { ...categoryAxis, tickfont: { size: 10 } }, margin: { t: 0, r: 8, b: 24, l: 80 } }}
      note="Missing hours remain gaps; exported means are not pooled." />
  </QuestionFrame>;
}

export default memo(TravelBoard);
