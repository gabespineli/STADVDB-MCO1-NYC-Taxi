import { memo, useEffect, useMemo, useState } from 'react';
import { AnswerTile, BentoChart, QuestionFrame } from '../components/Bento';
import { Select } from '../components/Chart';
import ZoneMap from '../components/ZoneMap';
import { detail, fmt, groupedSum, hourly, linkedMonthlyRows, matrix, maximum, monthKey, monthly, number, palette, rank, ratio, sum, unique, zoneId, zoneLabel } from '../analytics';
import { bars, categoryAxis, compactAxis, heatmap, monthlyPlot } from '../plots';
import type { Snapshot, Row } from '../types';
import type { ViewedRows } from '../questions';

function DemandBoard({ snapshot, onViewsChange }: { snapshot: Snapshot; onViewsChange: (views: ViewedRows) => void }) {
  const data = useMemo(() => ({ demand: detail(snapshot.reports.q1_demand.rows), hourly: detail(snapshot.reports.q1_hourly.rows),
    monthly: detail(snapshot.reports.q1_monthly.rows) }), [snapshot]);
  const boroughs = unique(data.hourly, 'borough');
  const [borough, setBorough] = useState(boroughs.includes('Manhattan') ? 'Manhattan' : boroughs[0] ?? '');
  const [focus, setFocus] = useState('');
  const focused = data.demand.find(row => zoneId(row) === focus);
  const selectZone = (id: string) => {
    const row = data.demand.find(row => zoneId(row) === id);
    setFocus(row ? id : '');
    if (row && boroughs.includes(String(row.borough))) setBorough(String(row.borough));
  };
  const hourlyRows = useMemo(() => data.hourly.filter(row => row.borough === borough), [data, borough]);
  const monthlySource = useMemo(() => focused ? linkedMonthlyRows(data.demand, data.monthly, focused) : data.monthly, [data, focused]);
  const viewed = useMemo(() => ({ q1_demand: data.demand, q1_hourly: hourlyRows, q1_monthly: monthlySource ?? data.monthly }), [data, hourlyRows, monthlySource]);
  useEffect(() => onViewsChange(viewed), [viewed, onViewsChange]);
  const top = rank(data.demand, 'total_filtered_pickups', 6), leader = focused ?? top[0];
  const outsideTop = focused && !top.some(row => zoneId(row) === focus);
  const ranking = outsideTop ? [...top.slice(0, 5), focused] : top;
  const share = leader ? ratio(number(leader.total_filtered_pickups), sum(data.demand, 'total_filtered_pickups')) : null;
  const months = monthly(monthlySource ?? data.monthly), allMonths = monthly(data.monthly), dates = allMonths.map(row => String(row.month));
  const peakHour = rank(hourlyRows, 'avg_weekday_hourly_pickups', 1)[0];
  const peakMonth = rank(months, 'late_night_pickups', 1)[0];
  const monthName = peakMonth ? new Date(String(peakMonth.month) + 'T00:00:00Z').toLocaleDateString('en-US', { month: 'short', timeZone: 'UTC' }) : '—';
  const monthScope = focused && monthlySource !== null ? String(focused.zone) : 'all zones';
  const zoneMonthlyScale = focused && monthlySource !== null;
  const topZones = rank(groupedSum(data.monthly, 'zone', ['late_night_pickups']), 'late_night_pickups', 5).map(row => String(row.zone));
  if (focused && monthlySource !== null && !topZones.includes(String(focused.zone))) topZones.push(String(focused.zone));
  const monthlyRows: Row[] = data.monthly.filter(row => monthKey(row) && topZones.includes(String(row.zone))).map(row => ({ ...row, month: monthKey(row) }));
  const monthLabels = dates.map(date => new Date(date + 'T00:00:00Z').toLocaleDateString('en-US', { month: 'short', timeZone: 'UTC' }));
  return <QuestionFrame id="demand" snapshot={snapshot}>
    <AnswerTile label={focused ? 'Selected demand pattern' : 'Demand pattern'} value={leader ? String(leader.zone) : 'Unavailable'}
      detail={share === null ? 'Awaiting demand results' : `${fmt(share, 1)}% of weekend / late-night pickups${focused ? '' : ' · leading zone'}`}
      context={`${borough} weekday peak: ${peakHour ? `${peakHour.hour}:00` : '—'} · ${monthScope} late-night peak: ${monthName}`} />
    <BentoChart area="zones" title="Where trips begin" subtitle={`${outsideTop ? 'Top five + selected zone' : 'Top six'} · weekend or late night`} height={175}
      controls={<Select label="Demand zone" value={focus} options={[{ value: '', label: 'All zones' }, ...rank(data.demand, 'total_filtered_pickups', data.demand.length).map(row => ({ value: zoneId(row), label: zoneLabel(row) }))]} onChange={selectZone} />}
      onSelect={selectZone} data={bars(ranking, 'zone', 'total_filtered_pickups').map(trace => ({ ...trace,
        customdata: [...ranking].reverse().map(row => [zoneId(row), ratio(number(row.total_filtered_pickups), sum(data.demand, 'total_filtered_pickups')), sum(data.demand, 'total_filtered_pickups'), row.borough]),
        marker: { color: palette[0], opacity: [...ranking].reverse().map(row => !focus || zoneId(row) === focus ? 1 : .3) },
        hovertemplate: '%{y} · %{customdata[3]}<br>%{x:,.0f} / %{customdata[2]:,} pickups (%{customdata[1]:.1f}%)<extra></extra>' }))}
      layout={{ showlegend: false, yaxis: { ...categoryAxis, tickfont: { size: 10 } }, xaxis: { ...compactAxis(), range: [0, maximum(data.demand, 'total_filtered_pickups') * 1.05] }, margin: { t: 0, r: 12, b: 24, l: 8 } }} />
    <div className="bento-cell cell-map">{snapshot.mapAvailable ? <ZoneMap rows={snapshot.reports.q1_demand.mapRows ?? []} height={285} selected={focus} onSelect={selectZone} /> :
      <div className="chart-panel"><h3>Taxi-zone demand</h3><p className="empty-state">Map boundaries unavailable. Use the zone ranking.</p></div>}</div>
    <BentoChart area="hourly" title="When demand peaks" subtitle="Pickups / represented day · NYC local time" height={285}
      controls={<Select label="Hourly borough" value={borough} options={boroughs} onChange={value => { setBorough(value); setFocus(''); }} />}
      data={['avg_weekday_hourly_pickups', 'avg_weekend_hourly_pickups'].map((key, index) => ({ type: 'scatter', mode: 'lines',
        x: Array.from({ length: 24 }, (_, hour) => hour), y: hourly(hourlyRows, key), name: ['Weekday', 'Weekend'][index],
        line: { color: palette[index], width: 2.5 }, connectgaps: false,
        hovertemplate: '%{x}:00<br>%{y:,.1f} pickups / represented day<extra>%{fullData.name}</extra>' }))}
      layout={{ xaxis: { ...compactAxis(), tickvals: [0, 6, 12, 18, 23], range: [0, 23] }, yaxis: { ...compactAxis(), range: [0, Math.max(maximum(data.hourly, 'avg_weekday_hourly_pickups'), maximum(data.hourly, 'avg_weekend_hourly_pickups')) * 1.05] }, margin: { t: 32, r: 8, b: 28, l: 44 } }}
      note={`${borough} borough context · averages use represented dates; missing hours remain gaps.`} />
    <BentoChart area="months" title="How volume changes" subtitle={`Monthly late-night pickups · ${monthScope}`} height={150} data={monthlyPlot(months)}
      layout={{ showlegend: false, xaxis: { type: 'date', tickformat: '%b', dtick: 'M2', fixedrange: true, range: dates.length ? [dates[0], dates.at(-1)] : undefined, showgrid: false }, yaxis: { ...compactAxis(), range: [0, maximum(zoneMonthlyScale ? data.monthly : allMonths, 'late_night_pickups') * 1.05] }, margin: { t: 4, r: 8, b: 24, l: 44 } }}
      note={monthlySource === null ? 'Ambiguous zone name in monthly export; showing all zones.' : focused && !months.length ? 'No monthly rows for this zone.' : 'Counts reflect different month lengths; zone selections share one scale.'} />
    <BentoChart area="consistency" title="Which zones stay busy" subtitle={`Monthly late-night pickups · ${focused && monthlySource !== null ? 'selected zone + leaders' : 'five busiest zones'}`} height={150}
      data={heatmap(matrix(monthlyRows, 'zone', 'month', 'late_night_pickups', topZones, dates), monthLabels, topZones, 'pickups', false, maximum(data.monthly, 'late_night_pickups'))}
      layout={{ yaxis: { ...categoryAxis, autorange: 'reversed', tickfont: { size: 10 } }, xaxis: { ...categoryAxis, tickfont: { size: 10 } }, margin: { t: 0, r: 8, b: 24, l: 8 } }} />
  </QuestionFrame>;
}

export default memo(DemandBoard);
