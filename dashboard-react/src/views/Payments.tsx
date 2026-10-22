import { useState } from 'react';
import Chart, { Select } from '../components/Chart';
import { matrix, number, palette, paymentMix, unique } from '../analytics';
import { categoryAxis, compactAxis, farePlot, heatmap, paymentPlot } from '../plots';
import type { Report, Row } from '../types';

export default function Payments({ report, rows }: { report: Report; rows: Row[] }) {
  const [basis, setBasis] = useState('Share'), [period, setPeriod] = useState('');
  const isFare = report.id === 'q2_fare', share = basis === 'Share';
  const control = <Select label="Measure" value={basis} options={['Share', 'Trips']} onChange={setBasis} />;
  if (isFare) return <div className="chart-grid">
    <Chart title="Payment mix by fare" subtitle={share ? 'Share of trips in each fare tier' : 'Trips in each fare tier'} controls={control}
      data={farePlot(rows, share)} height={360} layout={{ barmode: 'stack', xaxis: categoryAxis,
        yaxis: { ...compactAxis(share ? '%' : ''), ...(share ? { range: [0, 100] } : {}) }, margin: { t: 36, r: 16, b: 48, l: 48 } }} />
    <Chart title="Recorded tips by fare" subtitle="Returned mean tip per trip · all payment types" height={360}
      data={[{ type: 'bar', x: rows.map(row => row.fare_range), y: rows.map(row => number(row.avg_tip_amount)), marker: { color: palette[0] },
        hovertemplate: '%{x}<br>$%{y:.2f} recorded tip / trip<extra></extra>' }]}
      layout={{ showlegend: false, yaxis: { ...compactAxis(), tickprefix: '$' }, xaxis: categoryAxis }}
      note="Cash tips are not captured. These means do not represent total tipping across payment methods." />
  </div>;
  const periods = unique(rows, 'time_period');
  const selectedPeriod = periods.includes(period) ? period : periods[0] ?? '';
  const composition = paymentMix(rows, ['borough', 'time_period']);
  const selected = composition.filter(row => row.time_period === selectedPeriod);
  const boroughs = unique(rows, 'borough');
  const credit = composition.filter(row => row.payment_method === 'Credit Card');
  return <div className="chart-grid">
    <Chart title="Payment distribution" subtitle={selectedPeriod} controls={<div className="chart-controls">{control}
      <Select label="Period" value={selectedPeriod} options={periods} onChange={setPeriod} /></div>}
      data={paymentPlot(selected, share)} height={420} layout={{ barmode: 'stack', yaxis: categoryAxis,
        xaxis: { ...compactAxis(share ? '%' : ''), ...(share ? { range: [0, 100] } : {}) }, margin: { t: 90, r: 16, b: 32, l: 84 },
        legend: { orientation: 'h', x: 0, y: 1.32, font: { size: 10 } } }} />
    <Chart title="Credit-card share" subtitle="Share within each borough and time period" height={420}
      data={heatmap(matrix(credit, 'borough', 'time_period', 'share', boroughs, periods), periods, boroughs, '%')}
      layout={{ yaxis: { ...categoryAxis, autorange: 'reversed' }, xaxis: categoryAxis, margin: { t: 8, r: 20, b: 48, l: 90 } }} />
  </div>;
}
