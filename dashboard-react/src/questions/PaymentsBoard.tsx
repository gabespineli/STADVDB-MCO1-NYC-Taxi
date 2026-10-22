import { memo, useEffect, useMemo, useState } from 'react';
import { AnswerTile, BentoChart, QuestionFrame } from '../components/Bento';
import { Select } from '../components/Chart';
import { detail, fmt, matrix, number, palette, paymentMix, ratio, unique } from '../analytics';
import { categoryAxis, compactAxis, farePlot, focusCell, heatmap, paymentPlot } from '../plots';
import type { Row, Snapshot } from '../types';
import type { ViewedRows } from '../questions';

function PaymentsBoard({ snapshot, onViewsChange }: { snapshot: Snapshot; onViewsChange: (views: ViewedRows) => void }) {
  const data = useMemo(() => ({ fare: detail(snapshot.reports.q2_fare.rows), payment: detail(snapshot.reports.q2_payment.rows) }), [snapshot]);
  const [period, setPeriod] = useState('');
  const [fare, setFare] = useState(''), [borough, setBorough] = useState('');
  const periods = unique(data.payment, 'time_period'), selectedPeriod = periods.includes(period) ? period : periods[0] ?? '';
  const mix = paymentMix(data.payment, ['borough', 'time_period']);
  const card = mix.filter(row => row.payment_method === 'Credit Card'), boroughs = unique(data.payment, 'borough');
  const fareShares = data.fare.map((row): Row & { share: number | null } => ({ ...row, share: ratio(number(row.credit_card_trips), number(row.total_trips)) })).filter(row => row.share !== null).sort((a, b) => a.share! - b.share!);
  const lowest = fareShares[0], highest = fareShares.at(-1);
  const selectedFare = fareShares.find(row => row.fare_range === fare);
  const selectedCard = card.find(row => row.borough === borough && row.time_period === selectedPeriod);
  const finding = selectedFare ?? (borough ? selectedCard : lowest);
  const share = number(finding?.share);
  const focusPayment = (value: string) => {
    try { const [b, p] = JSON.parse(value); if (boroughs.includes(b) && periods.includes(p)) { setBorough(b); setPeriod(p); } } catch { /* Ignore non-data plot clicks. */ }
  };
  const cardHeatmap = heatmap(matrix(card, 'borough', 'time_period', 'share', boroughs, periods), periods, boroughs, '%').map(trace => ({ ...trace,
    customdata: boroughs.map(b => periods.map(p => { const row = card.find(item => item.borough === b && item.time_period === p); return [JSON.stringify([b, p]), number(row?.trip_count), number(row?.population_trips)]; })),
    hovertemplate: '%{y} · %{x}<br>%{z:.1f}% Credit Card<br>%{customdata[1]:,} / %{customdata[2]:,} trips<extra></extra>' }));
  const viewed = useMemo(() => ({ q2_fare: data.fare, q2_payment: data.payment.filter(row => row.time_period === selectedPeriod && (!borough || row.borough === borough)) }), [data, selectedPeriod, borough]);
  useEffect(() => onViewsChange(viewed), [viewed, onViewsChange]);
  return <QuestionFrame id="payments" snapshot={snapshot}>
    <AnswerTile label={selectedFare ? 'Selected fare · card share' : borough ? 'Selected place / time · card share' : 'Lowest fare-tier card share'} value={share === null ? 'Unavailable' : fmt(share, 1)} unit={share === null ? '' : '%'}
      detail={selectedFare ? String(selectedFare.fare_range) : borough ? `${borough} · ${selectedPeriod}` : lowest ? String(lowest.fare_range) : 'Awaiting payment results'}
      context={selectedFare || borough ? `${fmt(number(finding?.[selectedFare ? 'credit_card_trips' : 'trip_count']))} / ${fmt(number(finding?.[selectedFare ? 'total_trips' : 'population_trips']))} trips` : highest ? `${highest.fare_range} reaches ${fmt(highest.share, 1)}% · ${fmt(highest.share! - lowest.share!, 1)} pp spread` : undefined} />
    <BentoChart area="fare" title="How fare changes payment mix" subtitle="Share within each positive-fare tier" height={285}
      onSelect={setFare} data={farePlot(data.fare, true, fare)} layout={{ barmode: 'stack', yaxis: { ...compactAxis('%'), range: [0, 100] },
        xaxis: { ...categoryAxis, tickfont: { size: 10 } }, margin: { t: 32, r: 8, b: 36, l: 40 } }} />
    <BentoChart area="card" title="Where card payments are common" subtitle="Credit-card share by borough and time" height={285}
      onSelect={focusPayment} data={[...cardHeatmap, ...focusCell(selectedPeriod, borough)]}
      layout={{ xaxis: { ...categoryAxis, tickfont: { size: 10 } }, yaxis: { ...categoryAxis, autorange: 'reversed', tickfont: { size: 10 } }, margin: { t: 0, r: 8, b: 40, l: 72 } }} />
    <BentoChart area="tips" title="Recorded tips" subtitle="Mean per trip · all payment types" height={155}
      controls={<Select label="Fare tier" value={fare} options={[{ value: '', label: 'All fare tiers' }, ...data.fare.map(row => String(row.fare_range))]} onChange={setFare} />}
      onSelect={setFare}
      data={[{ type: 'bar', x: data.fare.map(row => row.fare_range), y: data.fare.map(row => number(row.avg_tip_amount)), customdata: data.fare.map(row => String(row.fare_range)), marker: { color: palette[0], opacity: data.fare.map(row => !fare || row.fare_range === fare ? 1 : .3) },
        hovertemplate: '%{x}<br>$%{y:.2f} recorded tip / trip<extra></extra>' }]}
      layout={{ showlegend: false, xaxis: { ...categoryAxis, tickfont: { size: 9 } }, yaxis: { ...compactAxis(), tickprefix: '$' }, margin: { t: 0, r: 4, b: 32, l: 28 } }}
      note="Cash tips are not captured." />
    <BentoChart area="distribution" title="Which methods each borough uses" subtitle="Share within each borough and selected time period" height={190}
      controls={<div className="chart-controls"><Select label="Payment borough" value={borough} options={[{ value: '', label: 'All boroughs' }, ...boroughs]} onChange={setBorough} />
        <Select label="Payment period" value={selectedPeriod} options={periods} onChange={setPeriod} /></div>}
      onSelect={setBorough} data={paymentPlot(mix.filter(row => row.time_period === selectedPeriod), true, borough)}
      layout={{ barmode: 'stack', yaxis: { ...categoryAxis, tickfont: { size: 10 } }, xaxis: { ...compactAxis('%'), range: [0, 100] },
        legend: { orientation: 'h', x: 0, y: 1.3, font: { size: 10 } }, margin: { t: 44, r: 12, b: 24, l: 72 } }} />
  </QuestionFrame>;
}

export default memo(PaymentsBoard);
