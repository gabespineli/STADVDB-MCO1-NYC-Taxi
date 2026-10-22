import { compact, fmt, number, palette, paymentColors, rank, sum } from './analytics';
import type { Row, Trace, PlotLayout } from './types';

export const hiddenLegend = { showlegend: false };
export const categoryAxis = { type: 'category', automargin: true, fixedrange: true, showgrid: false };
export const colorscale = [[0, '#f0f4f6'], [.3, '#b1c9d5'], [.65, '#5a8fa8'], [1, '#244d70']];
export function bars(rows: Row[], label: string, measure: string, color = palette[0]): Trace[] {
  const sorted = [...rows].reverse();
  return [{ type: 'bar', orientation: 'h', x: sorted.map(row => number(row[measure])), y: sorted.map(row => String(row[label])),
    marker: { color }, customdata: sorted.map(row => String(row[label])),
    hovertemplate: '%{y}<br>%{x:,.0f}<extra></extra>' }];
}
export function line(rows: Row[], x: string, y: string, name: string, color = palette[0]): Trace {
  return { type: 'scatter', mode: 'lines+markers', name, x: rows.map(row => row[x]), y: rows.map(row => number(row[y])),
    connectgaps: false, line: { color, width: 2.5 }, marker: { color, size: 5 },
    hovertemplate: '%{x}<br>%{y:,.1f}<extra>%{fullData.name}</extra>' };
}
export function monthlyPlot(rows: Row[]): Trace[] {
  return [{ ...line(rows, 'month', 'late_night_pickups', 'Pickups'), fill: 'tozeroy', fillcolor: 'rgba(36,77,112,.045)',
    hovertemplate: '%{x|%B %Y}<br>%{y:,.0f} pickups<extra></extra>' }];
}
export function farePlot(rows: Row[], share: boolean): Trace[] {
  const keys = ['credit_card_trips', 'cash_trips', 'other_payment_trips'];
  return keys.map((key, i) => ({ type: 'bar', name: ['Credit Card', 'Cash', 'Other'][i],
    x: rows.map(row => row.fare_range), y: rows.map(row => share ?
      (number(row[key]) !== null && number(row.total_trips) !== null && number(row.total_trips)! > 0 ? 100 * number(row[key])! / number(row.total_trips)! : null)
      : number(row[key])), marker: { color: [palette[0], palette[1], palette[4]][i] },
    hovertemplate: share ? '%{x}<br>%{y:.1f}%<extra>%{fullData.name}</extra>' : '%{x}<br>%{y:,.0f} trips<extra>%{fullData.name}</extra>' }));
}
export function paymentPlot(rows: Row[], share: boolean): Trace[] {
  return [...new Set(rows.map(row => String(row.payment_method)))].sort().map((method, index) => ({
    type: 'bar', orientation: 'h', name: method, y: rows.filter(row => row.payment_method === method).map(row => row.borough),
    x: rows.filter(row => row.payment_method === method).map(row => number(row[share ? 'share' : 'trip_count'])),
    marker: { color: paymentColors[method] ?? palette[index % palette.length] },
    hovertemplate: share ? '%{y}<br>%{x:.1f}%<extra>%{fullData.name}</extra>' : '%{y}<br>%{x:,.0f} trips<extra>%{fullData.name}</extra>',
  }));
}
export function heatmap(z: (number | null)[][], x: (string | number)[], y: string[], unit: string, diverging = false): Trace[] {
  return [{ type: 'heatmap', z, x, y, colorscale: diverging ? [[0, '#31867d'], [.5, '#f7f8f9'], [1, '#b76246']] : colorscale,
    ...(diverging ? { zmid: 0 } : {}), hoverongaps: false, xgap: 3, ygap: 3,
    colorbar: { thickness: 8, len: .8, outlinewidth: 0, tickfont: { size: 10 } },
    hovertemplate: `%{y}<br>%{x}<br>%{z:,.1f} ${unit}<extra></extra>` }];
}
export function pairedDuration(rows: Row[]): Trace[] {
  const x: (number | null)[] = [], y: (string | null)[] = [];
  rows.forEach(row => { x.push(number(row.off_peak_duration_min), number(row.rush_hour_duration_min), null); y.push(String(row.borough), String(row.borough), null); });
  return [
    { type: 'scatter', mode: 'lines', x, y, line: { color: '#cdd6de', width: 4 }, showlegend: false, hoverinfo: 'skip' },
    ...['off_peak_duration_min', 'rush_hour_duration_min'].map((key, i) => ({ type: 'scatter', mode: 'markers',
      name: ['Off-peak', 'Rush hour'][i], x: rows.map(row => number(row[key])), y: rows.map(row => row.borough),
      marker: { color: [palette[0], palette[1]][i], size: 10 }, hovertemplate: '%{y}<br>%{x:.1f} minutes<extra>%{fullData.name}</extra>' })),
  ];
}
export function compactAxis(unit = ''): PlotLayout { return { ticksuffix: unit, gridcolor: '#e9edf0', zeroline: false, fixedrange: true, automargin: true }; }
export function leaderNote(rows: Row[], key: string, label: string) {
  const leader = rank(rows, key, 1)[0], total = sum(rows, key);
  return leader && total !== null && total > 0 ? `${leader[label]} accounts for ${fmt(100 * number(leader[key])! / total, 1)}% of the selected pickups.` : '';
}
export function monthNote(rows: Row[]) {
  const peak = rank(rows, 'late_night_pickups', 1)[0];
  if (!peak) return '';
  const month = new Date(String(peak.month) + 'T00:00:00Z').toLocaleDateString('en-US', { month: 'long', timeZone: 'UTC' });
  return `Late-night volume peaks in ${month} at ${compact(number(peak.late_night_pickups))} pickups. Month lengths differ.`;
}
