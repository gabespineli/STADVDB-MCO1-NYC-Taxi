import { useEffect, useState } from 'react';
import Chart from './Chart';
import { maximum, number, ratio, sum, zoneId } from '../analytics';
import type { Row } from '../types';
import { colorscale } from '../plots';

let boundaries: unknown;
export default function ZoneMap({ rows, height = 430, selected = '', onSelect }: { rows: Row[]; height?: number; selected?: string; onSelect?: (id: string) => void }) {
  const [geojson, setGeojson] = useState<unknown>(boundaries), [error, setError] = useState(false);
  useEffect(() => {
    if (boundaries) return;
    const controller = new AbortController();
    fetch('/data/taxi-zones.json', { signal: controller.signal }).then(response => {
      if (!response.ok) throw new Error('Unavailable'); return response.json();
    }).then(data => { boundaries = data; setGeojson(data); }).catch(error => { if (error.name !== 'AbortError') setError(true); });
    return () => controller.abort();
  }, []);
  const mapped = rows.filter(row => row['Map status'] === 'Mapped');
  const focused = mapped.filter(row => zoneId(row) === selected);
  const total = sum(rows, 'total_filtered_pickups');
  const customdata = (items: Row[]) => items.map(row => [zoneId(row), ratio(number(row.total_filtered_pickups), total), total]);
  const hovertemplate = '%{text}<br>%{z:,.0f} / %{customdata[2]:,} pickups (%{customdata[1]:.1f}%)<extra></extra>';
  if (!geojson) return <section className="chart-panel map-placeholder"><h3>Taxi-zone demand</h3><p role="status">{error ? 'Boundaries unavailable. Use the zone ranking.' : 'Loading taxi-zone boundaries…'}</p></section>;
  return <Chart title="Taxi-zone demand" subtitle={focused.length ? `${focused[0].zone} selected · weekend / late-night` : 'Weekend / late-night pickups · select a zone'} height={height} headingLevel={3} onSelect={onSelect}
    data={[{ type: 'choroplethmap', geojson, featureidkey: 'id', locations: mapped.map(row => row.location_id),
      z: mapped.map(row => number(row.total_filtered_pickups)), text: mapped.map(row => row.zone),
      colorscale, zmin: 0, zmax: maximum(rows, 'total_filtered_pickups'), customdata: customdata(mapped), marker: { opacity: .9, line: { width: .35, color: '#fff' } },
      colorbar: { thickness: 8, len: .7, outlinewidth: 0 }, hovertemplate },
      ...focused.map(row => ({ type: 'choroplethmap', geojson, featureidkey: 'id', locations: [row.location_id], z: [number(row.total_filtered_pickups)], text: [row.zone],
        customdata: customdata([row]), colorscale: [[0, '#f6d56f'], [1, '#f6d56f']], showscale: false, marker: { opacity: .8, line: { width: 2, color: '#352a14' } }, hovertemplate }))]}
    layout={{ map: { style: 'white-bg', center: { lon: -73.94, lat: 40.72 }, zoom: 9 }, margin: { t: 0, b: 0, l: 0, r: 0 } }}
    note={`${mapped.length} of ${rows.length} groups mapped. Unmatched groups remain in totals and Data. Shading shows volume, not area density.`} />;
}
