import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { csv, detail, hourly, matrix, monthly, paymentMix, ratio, rush, sum } from './analytics.ts';
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
  assert.equal(ratio(0, 0), null);
  assert.equal(sum([{ count: 10 }, { count: null }], 'count'), null);
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
