import type { Row, Cell } from './types.ts';

const rollups: Record<string, string[]> = {
  borough: ['ALL BOROUGHS'], zone: ['Borough Subtotal', 'ALL ZONES'],
  time_period: ['All Time Periods'], payment_method: ['All Payment Methods'],
  fare_range: ['ALL FARE TIERS'], distance_bucket: ['All Distance Tiers'],
};
export const palette = ['#244d70', '#976100', '#31867d', '#91759d', '#778697', '#b76246', '#758b48', '#5f77ac'];
export const paymentColors: Record<string, string> = { 'Credit Card': palette[0], Cash: palette[1], Other: palette[4],
  'Flex Fare': palette[2], Dispute: palette[3], 'No Charge': palette[5], Unknown: palette[6], 'Voided Trip': palette[7] };
export const number = (value: Cell | undefined): number | null =>
  value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value)) ? Number(value) : null;
export const sum = (rows: Row[], key: string): number | null => {
  if (!rows.length || rows.some(row => number(row[key]) === null)) return null;
  return rows.reduce((total, row) => total + number(row[key])!, 0);
};
export const fmt = (value: number | null, digits = 0) => value === null || !Number.isFinite(value) ? '—' :
  new Intl.NumberFormat('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value);
export const compact = (value: number | null) => value === null || !Number.isFinite(value) ? '—' :
  new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(value);
export function detail(rows: Row[]): Row[] {
  return rows.filter(row => Object.entries(rollups).every(([key, labels]) => !(key in row) ||
    (row[key] !== null && !labels.includes(String(row[key])))) &&
    ['yr', 'qtr', 'mo'].every(key => !(key in row) || number(row[key]) !== null));
}
export const unique = (rows: Row[], key: string) => [...new Set(rows.map(row => row[key]).filter(x => x !== null && x !== undefined))].map(String).sort();
export function group(rows: Row[], keys: string[]): Map<string, Row[]> {
  const groups = new Map<string, Row[]>();
  rows.forEach(row => { const key = JSON.stringify(keys.map(k => row[k])); groups.set(key, [...(groups.get(key) ?? []), row]); });
  return groups;
}
export function groupedSum(rows: Row[], dimension: string, measures: string[]): Row[] {
  return [...group(rows, [dimension]).values()].map(items => Object.fromEntries([
    [dimension, items[0][dimension]], ...measures.map(key => [key, sum(items, key)]),
  ]));
}
export function rank(rows: Row[], measure: string, limit = 12): Row[] {
  return [...rows].filter(row => number(row[measure]) !== null).sort((a, b) => number(b[measure])! - number(a[measure])!).slice(0, limit);
}
export const ratio = (numerator: number | null, denominator: number | null) =>
  numerator === null || denominator === null || denominator <= 0 ? null : 100 * numerator / denominator;
export function rush(rows: Row[]): Row[] {
  return rows.map(row => {
    const peak = number(row.rush_hour_duration_min), off = number(row.off_peak_duration_min);
    const extra = peak !== null && off !== null ? peak - off : null;
    return { ...row, extra, percent: ratio(extra, off) };
  });
}
export function paymentMix(rows: Row[], dimensions: string[]): Row[] {
  return [...group(rows, dimensions).values()].flatMap(items => {
    const total = sum(items, 'trip_count');
    return items.map(row => ({ ...row, share: ratio(number(row.trip_count), total) }));
  });
}
export function monthKey(row: Row): string | null {
  const yr = number(row.yr), mo = number(row.mo);
  return yr !== null && mo !== null && Number.isInteger(yr) && Number.isInteger(mo) && mo >= 1 && mo <= 12
    ? `${yr}-${String(mo).padStart(2, '0')}-01` : null;
}
export function monthly(rows: Row[]): Row[] {
  const valid = detail(rows).filter(row => monthKey(row));
  const totals = groupedSum(valid.map(row => ({ ...row, month: monthKey(row) })), 'month', ['late_night_pickups']);
  const values = new Map(totals.map(row => [String(row.month), row.late_night_pickups]));
  const keys = [...values.keys()].sort();
  if (!keys.length) return [];
  const result: Row[] = [];
  const current = new Date(keys[0] + 'T00:00:00Z'), last = new Date(keys.at(-1)! + 'T00:00:00Z');
  while (current <= last) {
    const month = current.toISOString().slice(0, 10);
    result.push({ month, late_night_pickups: values.get(month) ?? null });
    current.setUTCMonth(current.getUTCMonth() + 1);
  }
  return result;
}
export function hourly(rows: Row[], measure: string): (number | null)[] {
  const byHour = new Map<number, number | null>();
  rows.forEach(row => {
    const hour = number(row.hour);
    if (hour === null || byHour.has(hour)) throw new Error('Several groups share an hour. Narrow the selected groups.');
    byHour.set(hour, number(row[measure]));
  });
  return Array.from({ length: 24 }, (_, hour) => byHour.get(hour) ?? null);
}
export function matrix(rows: Row[], rowKey: string, columnKey: string, measure: string, labels: string[], columns: (string | number)[]) {
  const cells = new Map<string, number | null>();
  for (const row of rows) {
    const key = JSON.stringify([String(row[rowKey]), String(row[columnKey])]);
    if (cells.has(key)) throw new Error('Several groups share a heatmap cell. Narrow the selected groups.');
    cells.set(key, number(row[measure]));
  }
  return labels.map(label => columns.map(column => cells.get(JSON.stringify([label, String(column)])) ?? null));
}
export function csv(rows: Row[], columns: string[]) {
  const cell = (value: Cell | undefined) => {
    const text = value === null || value === undefined ? '\\N' : String(value);
    // Prevent spreadsheet formula interpretation of string labels.
    const safe = typeof value === 'string' && /^[=+\-@\t\r]/.test(text) ? `'${text}` : text;
    return `"${safe.replaceAll('"', '""')}"`;
  };
  return '\uFEFF' + [columns.map(cell).join(','), ...rows.map(row => columns.map(key => cell(row[key])).join(','))].join('\r\n');
}
