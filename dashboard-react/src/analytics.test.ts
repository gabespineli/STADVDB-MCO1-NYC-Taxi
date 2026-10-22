import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { categoryColor, csv, detail, hourly, linkedMonthlyRows, matrix, monthly, paymentMix, ratio, rush, selectionValue, sum, zoneId } from './analytics.ts';
import { farePlot, heatmap, paymentPlot } from './plots.ts';
import type { Snapshot } from './types.ts';

test('rollups and unknown monthly grains cannot inflate detail totals', () => {
  const rows = [{ borough: 'Manhattan', zone: 'Midtown', count: 10 }, { borough: 'ALL BOROUGHS', zone: 'ALL ZONES', count: 10 },
    { borough: 'Manhattan', zone: 'Borough Subtotal', count: 10 }];
  assert.equal(sum(detail(rows), 'count'), 10);
  assert.equal(detail([{ yr: '2025', qtr: '1', mo: 'Quarter Subtotal' }]).length, 0);
});
test('missing months and hours stay unknown while observed zero stays zero', () => {
  const rows = [{ yr: '2025', qtr: '1', mo: '1', late_night_pickups: 10 }, { yr: '2025', qtr: '1', mo: '3', late_night_pickups: 0 }];
  assert.deepEqual(monthly(rows).map(row => row.late_night_pickups), [10, null, 0]);
  assert.deepEqual(hourly([{ hour: 0, value: 0 }, { hour: 2, value: 5 }], 'value').slice(0, 3), [0, null, 5]);
});
test('payment denominators remain local to each borough and time population', () => {
  const mix = paymentMix([{ borough: 'A', time: 'Rush', trip_count: 80 }, { borough: 'A', time: 'Rush', trip_count: 20 },
    { borough: 'B', time: 'Rush', trip_count: 5 }, { borough: 'B', time: 'Rush', trip_count: 5 }], ['borough', 'time']);
  assert.deepEqual(mix.map(row => row.share), [80, 20, 50, 50]);
  assert.deepEqual(mix.map(row => row.population_trips), [100, 100, 10, 10]);
  assert.equal(ratio(0, 0), null);
  assert.equal(sum([{ count: 10 }, { count: null }], 'count'), null);
});

test('zone coordination rejects ambiguous monthly names and preserves exact identities', () => {
  const queens = { borough: 'Queens', zone: 'Airport' }, bronx = { borough: 'Bronx', zone: 'Airport' };
  const month = { zone: 'Airport', yr: 2025, mo: 1, late_night_pickups: 10 };
  assert.deepEqual(linkedMonthlyRows([queens], [month], queens), [month]);
  assert.equal(linkedMonthlyRows([queens, bronx], [month], queens), null);
  assert.deepEqual(linkedMonthlyRows([queens], [], queens), []);
  assert.notEqual(zoneId(queens), zoneId(bronx));
  assert.notEqual(zoneId({ borough: 'A · B', zone: 'C' }), zoneId({ borough: 'A', zone: 'B · C' }));
});

test('plot selections retain identity when hover data adds counts, and ignore numeric cells', () => {
  const id = zoneId({ borough: 'Queens', zone: 'Airport' });
  assert.equal(selectionValue([id, 10, 100]), id);
  assert.equal(selectionValue('Cash'), 'Cash');
  for (const value of [undefined, null, [], 42, [42, 'misleading']]) assert.equal(selectionValue(value), undefined);
});

test('share heatmaps always span 0-100 and travel differences remain symmetric across selections', () => {
  const shares = heatmap([[55, 75]], ['AM', 'PM'], ['Queens'], '%')[0];
  assert.deepEqual([shares.zmin, shares.zmax], [0, 100]);
  const full = heatmap([[-2, 7]], ['AM', 'PM'], ['Queens'], 'min', true, 7)[0];
  const subset = heatmap([[1]], ['AM'], ['Queens'], 'min', true, 7)[0];
  assert.deepEqual([full.zmin, full.zmid, full.zmax], [-7, 0, 7]);
  assert.deepEqual([subset.zmin, subset.zmid, subset.zmax], [-7, 0, 7]);
});

test('share hover evidence uses the matching local numerator and denominator', () => {
  const fare = farePlot([{ fare_range: 'Tier', total_trips: 100, credit_card_trips: 75, cash_trips: 20, other_payment_trips: 5 }], true);
  assert.deepEqual(fare.map(trace => trace.customdata), [[['Tier', 75, 100]], [['Tier', 20, 100]], [['Tier', 5, 100]]]);
  const rows = paymentMix([{ borough: 'Queens', time: 'AM', payment_method: 'Credit Card', trip_count: 8 },
    { borough: 'Queens', time: 'AM', payment_method: 'Cash', trip_count: 2 }], ['borough', 'time']);
  const card = paymentPlot(rows, true).find(trace => trace.name === 'Credit Card')!;
  assert.deepEqual(card.customdata, [['Queens', 8, 10]]);
  assert.deepEqual(card.x, [80]);
  const unknown = paymentMix([{ borough: 'Queens', trip_count: 8 }, { borough: 'Queens', trip_count: null }], ['borough']);
  assert.ok(unknown.every(row => row.share === null && row.population_trips === null));
});

test('category colors stay stable when other methods or periods disappear', () => {
  const rows = [{ borough: 'A', payment_method: 'New method', share: 10 }, { borough: 'A', payment_method: 'Cash', share: 90 }];
  const all = paymentPlot(rows, true), one = paymentPlot(rows.slice(0, 1), true);
  assert.deepEqual(all.find(trace => trace.name === 'New method')!.marker, one[0].marker);
  assert.equal(categoryColor('Late Night'), categoryColor('Late Night'));
  assert.notEqual(categoryColor('Morning Rush'), categoryColor('Evening Rush'));
});
test('rush-hour differences retain negative differences and invalid percentage baselines', () => {
  const differences = rush([{ rush_hour_duration_min: 5, off_peak_duration_min: 10 }, { rush_hour_duration_min: 5, off_peak_duration_min: 0 }]);
  assert.deepEqual(differences.map(row => [row.extra, row.percent]), [[-5, -50], [5, null]]);
});
test('duplicate groups are rejected rather than pooling exported group averages', () => {
  assert.throws(() => hourly([{ hour: 8, mean: 2 }, { hour: 8, mean: 100 }], 'mean'));
  assert.throws(() => matrix([{ zone: 'A', hour: 8, speed: 10 }, { zone: 'A', hour: 8, speed: 100 }], 'zone', 'hour', 'speed', ['A'], [8]));
});
test('downloads preserve SQL nulls, lookup labels, and protect spreadsheet formula labels', () => {
  const output = csv([{ name: 'N/A', value: null }, { name: '=SUM(1,2)', value: -5 }], ['name', 'value']);
  assert.ok(output.includes('"N/A","\\N"'));
  assert.ok(output.includes('"\'=SUM(1,2)","-5"'));
});
test('prepared actual saved exports reconcile fare shares and exclude monthly rollups', () => {
  const snapshot: Snapshot = JSON.parse(readFileSync(new URL('../public/data/snapshot.json', import.meta.url), 'utf8'));
  assert.equal(Object.keys(snapshot.reports).length, 7);
  for (const report of Object.values(snapshot.reports)) {
    if (report.status === 'Ready') assert.equal(report.rows.length, report.source!.rowCount);
  }
  const fare = detail(snapshot.reports.q2_fare.rows);
  if (fare.length) {
    assert.equal(sum(fare, 'total_trips'), sum(fare, 'credit_card_trips')! + sum(fare, 'cash_trips')! + sum(fare, 'other_payment_trips')!);
  }
  const source = detail(snapshot.reports.q1_monthly.rows);
  assert.equal(sum(monthly(source), 'late_night_pickups'), sum(source, 'late_night_pickups'));
});
