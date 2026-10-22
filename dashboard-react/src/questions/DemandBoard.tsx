import { memo, useEffect, useMemo, useState } from 'react';
import { AnswerTile, BentoChart, QuestionFrame } from '../components/Bento';
import { Select } from '../components/Chart';
import ZoneMap from '../components/ZoneMap';
import { compact, detail, fmt, groupedSum, hourly, matrix, monthKey, monthly, number, palette, rank, ratio, sum, unique } from '../analytics';
import { bars, categoryAxis, compactAxis, heatmap, monthlyPlot } from '../plots';
import type { Snapshot, Row } from '../types';
import type { ViewedRows } from '../questions';

function DemandBoard({ snapshot, onViewsChange }: { snapshot: Snapshot; onViewsChange: (views: ViewedRows) => void }) {
  const data = useMemo(() => ({ demand: detail(snapshot.reports.q1_demand.rows), hourly: detail(snapshot.reports.q1_hourly.rows),
    monthly: detail(snapshot.reports.q1_monthly.rows) }), [snapshot]);
  const boroughs = unique(data.hourly, 'borough');
  const [borough, setBorough] = useState(boroughs.includes('Manhattan') ? 'Manhattan' : boroughs[0] ?? '');
  const hourlyRows = useMemo(() => data.hourly.filter(row => row.borough === borough), [data, borough]);
  const viewed = useMemo(() => ({ q1_demand: data.demand, q1_hourly: hourlyRows, q1_monthly: data.monthly }), [data, hourlyRows]);
  useEffect(() => onViewsChange(viewed), [viewed, onViewsChange]);
  const top = rank(data.demand, 'total_filtered_pickups', 6), leader = top[0];
  const share = leader ? ratio(number(leader.total_filtered_pickups), sum(data.demand, 'total_filtered_pickups')) : null;
  const months = monthly(data.monthly), dates = months.map(row => String(row.month));
  const topZones = rank(groupedSum(data.monthly, 'zone', ['late_night_pickups']), 'late_night_pickups', 5).map(row => String(row.zone));
  const monthlyRows: Row[] = data.monthly.filter(row => monthKey(row) && topZones.includes(String(row.zone))).map(row => ({ ...row, month: monthKey(row) }));
  const monthLabels = dates.map(date => new Date(date + 'T00:00:00Z').toLocaleDateString('en-US', { month: 'short', timeZone: 'UTC' }));
  return <QuestionFrame id="demand" snapshot={snapshot}>
    <AnswerTile label="Leading pickup zone" value={leader ? String(leader.zone) : 'Unavailable'}
      detail={share === null ? 'Awaiting demand results' : `${fmt(share, 1)}% of weekend / late-night pickups`}
      context={`${compact(sum(data.demand, 'total_filtered_pickups'))} pickups across all reported zones`} />
    <BentoChart area="zones" title="Where trips begin" subtitle="Top six · weekend or late night" height={175}
      data={bars(top, 'zone', 'total_filtered_pickups')} layout={{ showlegend: false, yaxis: categoryAxis, xaxis: compactAxis(), margin: { t: 0, r: 12, b: 24, l: 8 } }} />
    <div className="bento-cell cell-map">{snapshot.mapAvailable ? <ZoneMap rows={snapshot.reports.q1_demand.mapRows ?? []} height={285} /> :
      <div className="chart-panel"><h3>Taxi-zone demand</h3><p className="empty-state">Map boundaries unavailable. Use the zone ranking.</p></div>}</div>
    <BentoChart area="hourly" title="When demand peaks" subtitle="Pickups / represented day · NYC local time" height={285}
      controls={<Select label="Hourly borough" value={borough} options={boroughs} onChange={setBorough} />}
      data={['avg_weekday_hourly_pickups', 'avg_weekend_hourly_pickups'].map((key, index) => ({ type: 'scatter', mode: 'lines',
        x: Array.from({ length: 24 }, (_, hour) => hour), y: hourly(hourlyRows, key), name: ['Weekday', 'Weekend'][index],
        line: { color: palette[index], width: 2.5 }, connectgaps: false,
        hovertemplate: '%{x}:00<br>%{y:,.1f} pickups / represented day<extra>%{fullData.name}</extra>' }))}
      layout={{ xaxis: { ...compactAxis(), tickvals: [0, 6, 12, 18, 23], range: [0, 23] }, yaxis: compactAxis(), margin: { t: 32, r: 8, b: 28, l: 44 } }}
      note="Averages use dates represented in each group; missing hours remain gaps." />
    <BentoChart area="months" title="How volume changes" subtitle="Monthly late-night pickups · all zones" height={150} data={monthlyPlot(months)}
      layout={{ showlegend: false, xaxis: { type: 'date', tickformat: '%b', dtick: 'M2', fixedrange: true, showgrid: false }, yaxis: compactAxis(), margin: { t: 4, r: 8, b: 24, l: 44 } }}
      note="Counts reflect different month lengths." />
    <BentoChart area="consistency" title="Which zones stay busy" subtitle="Monthly late-night pickups · five busiest zones" height={150}
      data={heatmap(matrix(monthlyRows, 'zone', 'month', 'late_night_pickups', topZones, dates), monthLabels, topZones, 'pickups')}
      layout={{ yaxis: { ...categoryAxis, autorange: 'reversed', tickfont: { size: 10 } }, xaxis: { ...categoryAxis, tickfont: { size: 10 } }, margin: { t: 0, r: 8, b: 24, l: 8 } }} />
  </QuestionFrame>;
}

export default memo(DemandBoard);
