import { useEffect, useMemo, useState } from 'react';
import { compact, detail, fmt, group, number, rank, ratio, rush, sum, unique } from '../analytics';
import { Metric, Select } from '../components/Chart';
import Demand from './Demand';
import Payments from './Payments';
import Travel from './Travel';
import type { Report, Row } from '../types';

export default function ReportPage({ report, mapAvailable, onRowsChange }: { report: Report; mapAvailable: boolean; onRowsChange: (rows: Row[]) => void }) {
  const raw = useMemo(() => detail(report.rows), [report.rows]);
  const [borough, setBorough] = useState(report.id === 'q1_hourly' && unique(raw, 'borough').includes('Manhattan') ? 'Manhattan' : 'All boroughs');
  const [zone, setZone] = useState(''), [distance, setDistance] = useState(''), [measure, setMeasure] = useState('Speed (mph)');
  const boroughRows = useMemo(() => borough === 'All boroughs' ? raw : raw.filter(row => row.borough === borough), [raw, borough]);
  const zoneOptions = useMemo(() => report.id !== 'q3_location' ? [] : rank(
    [...group(boroughRows, ['borough', 'zone']).values()].map(items => ({
      label: `${items[0].zone} · ${items[0].borough}`, trip_count: sum(items, 'trip_count'),
    })), 'trip_count', Number.MAX_SAFE_INTEGER).map(row => String(row.label)), [boroughRows, report.id]);
  const selectedZone = zoneOptions.includes(zone) ? zone : zoneOptions[0] ?? '';
  const distances = unique(boroughRows, 'distance_bucket');
  const selectedDistance = distances.includes(distance) ? distance : distances[0] ?? '';
  const rows = useMemo(() => boroughRows.filter(row =>
    (report.id !== 'q3_location' || `${row.zone} · ${row.borough}` === selectedZone) &&
    (report.id !== 'q3_comparison' || row.distance_bucket === selectedDistance)), [boroughRows, report.id, selectedZone, selectedDistance]);
  useEffect(() => { onRowsChange(report.id === 'q3_comparison' ? boroughRows : rows); }, [rows, boroughRows, report.id, onRowsChange]);
  if (report.status !== 'Ready') return <div className="empty-state" role="status"><h2>Export unavailable</h2><p>{report.status}</p></div>;
  let metricLabel = '', metricValue = '', secondaryLabel = '', secondaryValue = '';
  switch (report.id) {
    case 'q1_demand': metricLabel = 'Weekend / late-night pickups'; metricValue = compact(sum(rows, 'total_filtered_pickups')); secondaryLabel = 'Pickup zones'; secondaryValue = fmt(rows.length); break;
    case 'q1_hourly': metricLabel = 'Pickups in selected groups'; {
      const weekday = sum(rows, 'weekday_pickups'), weekend = sum(rows, 'weekend_pickups');
      metricValue = compact(weekday !== null && weekend !== null ? weekday + weekend : null);
    } secondaryLabel = 'Peak weekday pickups / represented day'; secondaryValue = fmt(number(rank(rows, 'avg_weekday_hourly_pickups', 1)[0]?.avg_weekday_hourly_pickups), 1); break;
    case 'q1_monthly': metricLabel = 'Late-night pickups'; metricValue = compact(sum(rows, 'late_night_pickups')); secondaryLabel = 'Pickup zones'; secondaryValue = fmt(unique(rows, 'zone').length); break;
    case 'q2_fare': metricLabel = 'Positive-fare trips'; metricValue = compact(sum(rows, 'total_trips')); secondaryLabel = 'Credit-card share'; {
      const share = ratio(sum(rows, 'credit_card_trips'), sum(rows, 'total_trips')); secondaryValue = share === null ? '—' : `${fmt(share, 1)}%`;
    } break;
    case 'q2_payment': metricLabel = 'Positive-fare trips'; metricValue = compact(sum(rows, 'trip_count')); secondaryLabel = 'Payment methods'; secondaryValue = fmt(unique(rows, 'payment_method').length); break;
    case 'q3_comparison': metricLabel = 'Largest selected rush-hour gap'; {
      const gap = number(rank(rush(rows), 'extra', 1)[0]?.extra); metricValue = gap === null ? '—' : `${gap >= 0 ? '+' : ''}${fmt(gap, 1)} min`;
    } secondaryLabel = 'Comparison groups'; secondaryValue = fmt(rows.length); break;
    default: metricLabel = 'Trips in selected zone'; metricValue = compact(sum(rows, 'trip_count')); secondaryLabel = 'Hourly groups'; secondaryValue = fmt(rows.length);
  }
  return <>
    <div className="report-toolbar">
      <div className="report-metrics"><Metric label={metricLabel} value={metricValue} /><Metric label={secondaryLabel} value={secondaryValue} /></div>
      <div className="filters">
        {raw.some(row => 'borough' in row) && <Select label="Borough" value={borough} options={['All boroughs', ...unique(raw, 'borough')]} onChange={setBorough} />}
        {report.id === 'q3_comparison' && <Select label="Distance" value={selectedDistance} options={distances} onChange={setDistance} />}
        {report.id === 'q3_location' && <Select label="Zone" value={selectedZone} options={zoneOptions} onChange={setZone} />}
      </div>
    </div>
    {!rows.length ? <p role="status" className="empty-state">No matching detail groups.</p> :
      report.section === 'Q1' ? <Demand report={report} rows={rows} mapAvailable={mapAvailable} /> :
      report.section === 'Q2' ? <Payments report={report} rows={rows} /> :
      <Travel report={report} rows={rows} allRows={boroughRows} measure={measure} setMeasure={setMeasure} />}
    <p className="page-note">{report.scope}</p>
  </>;
}
