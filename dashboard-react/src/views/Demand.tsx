import Chart from '../components/Chart';
import ZoneMap from '../components/ZoneMap';
import { groupedSum, hourly, matrix, monthKey, monthly, number, palette, rank, unique } from '../analytics';
import { bars, categoryAxis, compactAxis, heatmap, leaderNote, line, monthlyPlot, monthNote } from '../plots';
import type { Report, Row } from '../types';

export default function Demand({ report, rows, mapAvailable }: { report: Report; rows: Row[]; mapAvailable: boolean }) {
  if (report.id === 'q1_demand') {
    const top = rank(rows, 'total_filtered_pickups', 12).map(row => ({ ...row, label: row.zone }));
    const boroughs = groupedSum(rows, 'borough', ['weekday_late_night_pickups', 'weekend_late_night_pickups', 'all_weekend_pickups']);
    const selectedKeys = new Set(rows.map(row => JSON.stringify([row.borough, row.zone])));
    const mapRows = (report.mapRows ?? []).filter(row => selectedKeys.has(JSON.stringify([row.borough, row.zone])));
    return <div className="chart-grid">
      <Chart title="Top pickup zones" subtitle="12 busiest selected zones · weekend or late night" data={bars(top, 'label', 'total_filtered_pickups')}
        height={430} layout={{ showlegend: false, yaxis: categoryAxis, xaxis: compactAxis(), margin: { t: 4, b: 28, l: 16, r: 20 } }}
        note={leaderNote(rows, 'total_filtered_pickups', 'zone')} />
      {mapAvailable && <ZoneMap rows={mapRows} />}
      <div className="span-all"><Chart title="Borough demand" subtitle="Comparison categories overlap" height={300}
        data={['weekday_late_night_pickups', 'weekend_late_night_pickups', 'all_weekend_pickups'].map((key, i) => ({ type: 'bar',
          x: boroughs.map(row => row.borough), y: boroughs.map(row => number(row[key])),
          name: ['Weekday late night', 'Weekend late night', 'All weekend'][i], marker: { color: palette[i] },
          hovertemplate: '%{x}<br>%{y:,.0f} pickups<extra>%{fullData.name}</extra>' }))}
        layout={{ barmode: 'group', xaxis: categoryAxis, yaxis: compactAxis(), margin: { t: 36, b: 40, l: 48, r: 12 } }}
        note="Weekend late-night pickups are included in all-weekend pickups. These series must not be added." /></div>
    </div>;
  }
  if (report.id === 'q1_hourly') {
    return <><div className="chart-grid hourly-grid">{unique(rows, 'borough').map(borough => {
      const selected = rows.filter(row => row.borough === borough);
      return <Chart key={borough} title={borough} subtitle="Pickups per represented day · NYC local time" height={270}
        data={['avg_weekday_hourly_pickups', 'avg_weekend_hourly_pickups'].map((key, i) => ({ type: 'scatter', mode: 'lines+markers',
          x: Array.from({ length: 24 }, (_, hour) => hour), y: hourly(selected, key), name: ['Weekday', 'Weekend'][i],
          line: { color: palette[i], width: 2.5 }, marker: { size: 4 }, connectgaps: false,
          hovertemplate: '%{x}:00<br>%{y:,.1f} pickups / day<extra>%{fullData.name}</extra>' }))}
        layout={{ xaxis: { ...compactAxis(), tickvals: [0, 6, 12, 18, 23], range: [0, 23] }, yaxis: compactAxis(),
          margin: { t: 36, b: 32, l: 48, r: 12 } }} />;
    })}</div><p className="page-note">Each borough uses its own vertical scale. Averages use represented dates; missing hours remain gaps.</p></>;
  }
  const months = monthly(rows), dates = months.map(row => String(row.month));
  const topZones = rank(groupedSum(rows, 'zone', ['late_night_pickups']), 'late_night_pickups', 12).map(row => String(row.zone));
  const monthlyRows: Row[] = rows.filter(row => monthKey(row)).map(row => ({ ...row, month: monthKey(row) }));
  const monthLabels = dates.map(date => new Date(date + 'T00:00:00Z').toLocaleDateString('en-US', { month: 'short', year: '2-digit', timeZone: 'UTC' }));
  return <div className="chart-grid">
    <Chart title="Late-night volume" subtitle="All selected zones" data={monthlyPlot(months)} height={300}
      layout={{ showlegend: false, xaxis: { type: 'date', tickformat: '%b', showgrid: false }, yaxis: compactAxis() }} note={monthNote(months)} />
    <Chart title="Leading zone profiles" subtitle="Three highest-volume selected zones" height={300}
      data={topZones.slice(0, 3).map((zone, i) => line(monthly(monthlyRows.filter(row => row.zone === zone)), 'month', 'late_night_pickups', zone, palette[i]))}
      layout={{ xaxis: { type: 'date', tickformat: '%b', showgrid: false }, yaxis: compactAxis(),
        legend: { orientation: 'h', y: -.22, x: 0, font: { size: 10 } }, margin: { t: 12, b: 76, l: 44, r: 16 } }} />
    <div className="span-all"><Chart title="Monthly consistency" subtitle="12 busiest selected zones · pickups" height={420}
      data={heatmap(matrix(monthlyRows.filter(row => topZones.includes(String(row.zone))), 'zone', 'month', 'late_night_pickups', topZones, dates), monthLabels, topZones, 'pickups')}
      layout={{ yaxis: { ...categoryAxis, autorange: 'reversed' }, xaxis: categoryAxis, margin: { t: 8, l: 16, b: 40, r: 20 } }} /></div>
  </div>;
}
