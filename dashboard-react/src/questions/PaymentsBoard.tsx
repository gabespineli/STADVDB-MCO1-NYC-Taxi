import { memo, useEffect, useMemo, useState } from 'react';
import { AnswerTile, BentoChart, QuestionFrame } from '../components/Bento';
import { Select } from '../components/Chart';
import { detail, fmt, matrix, number, palette, paymentMix, ratio, sum, unique } from '../analytics';
import { categoryAxis, compactAxis, farePlot, heatmap, paymentPlot } from '../plots';
import type { Snapshot } from '../types';
import type { ViewedRows } from '../questions';

function PaymentsBoard({ snapshot, onViewsChange }: { snapshot: Snapshot; onViewsChange: (views: ViewedRows) => void }) {
  const data = useMemo(() => ({ fare: detail(snapshot.reports.q2_fare.rows), payment: detail(snapshot.reports.q2_payment.rows) }), [snapshot]);
  const viewed = useMemo(() => ({ q2_fare: data.fare, q2_payment: data.payment }), [data]);
  useEffect(() => onViewsChange(viewed), [viewed, onViewsChange]);
  const [period, setPeriod] = useState('');
  const periods = unique(data.payment, 'time_period'), selectedPeriod = periods.includes(period) ? period : periods[0] ?? '';
  const mix = paymentMix(data.payment, ['borough', 'time_period']);
  const card = mix.filter(row => row.payment_method === 'Credit Card'), boroughs = unique(data.payment, 'borough');
  const share = ratio(sum(data.fare, 'credit_card_trips'), sum(data.fare, 'total_trips'));
  return <QuestionFrame id="payments" snapshot={snapshot}>
    <AnswerTile label="Credit-card share" value={share === null ? 'Unavailable' : fmt(share, 1)} unit={share === null ? '' : '%'}
      detail="of positive-fare trips" context="Fare-tier query population" />
    <BentoChart area="fare" title="How fare changes payment mix" subtitle="Share within each positive-fare tier" height={285}
      data={farePlot(data.fare, true)} layout={{ barmode: 'stack', yaxis: { ...compactAxis('%'), range: [0, 100] },
        xaxis: { ...categoryAxis, tickfont: { size: 10 } }, margin: { t: 32, r: 8, b: 36, l: 40 } }} />
    <BentoChart area="card" title="Where card payments are common" subtitle="Credit-card share by borough and time" height={285}
      data={heatmap(matrix(card, 'borough', 'time_period', 'share', boroughs, periods), periods, boroughs, '%')}
      layout={{ xaxis: { ...categoryAxis, tickfont: { size: 10 } }, yaxis: { ...categoryAxis, autorange: 'reversed', tickfont: { size: 10 } }, margin: { t: 0, r: 8, b: 40, l: 72 } }} />
    <BentoChart area="tips" title="Recorded tips" subtitle="Mean per trip · all payment types" height={155}
      data={[{ type: 'bar', x: data.fare.map(row => row.fare_range), y: data.fare.map(row => number(row.avg_tip_amount)), marker: { color: palette[0] },
        hovertemplate: '%{x}<br>$%{y:.2f} recorded tip / trip<extra></extra>' }]}
      layout={{ showlegend: false, xaxis: { ...categoryAxis, tickfont: { size: 9 } }, yaxis: { ...compactAxis(), tickprefix: '$' }, margin: { t: 0, r: 4, b: 32, l: 28 } }}
      note="Cash tips are not captured." />
    <BentoChart area="distribution" title="Which methods each borough uses" subtitle="Share within each borough and selected time period" height={190}
      controls={<Select label="Payment period" value={selectedPeriod} options={periods} onChange={setPeriod} />}
      data={paymentPlot(mix.filter(row => row.time_period === selectedPeriod), true)}
      layout={{ barmode: 'stack', yaxis: { ...categoryAxis, tickfont: { size: 10 } }, xaxis: { ...compactAxis('%'), range: [0, 100] },
        legend: { orientation: 'h', x: 0, y: 1.3, font: { size: 10 } }, margin: { t: 44, r: 12, b: 24, l: 72 } }} />
  </QuestionFrame>;
}

export default memo(PaymentsBoard);
