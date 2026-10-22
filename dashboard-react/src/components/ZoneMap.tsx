import { useEffect, useState } from 'react';
import Chart from './Chart';
import { number } from '../analytics';
import type { Row } from '../types';
import { colorscale } from '../plots';

let boundaries: unknown;
export default function ZoneMap({ rows, height = 430 }: { rows: Row[]; height?: number }) {
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
  if (!geojson) return <section className="chart-panel map-placeholder"><h3>Taxi-zone demand</h3><p role="status">{error ? 'Boundaries unavailable. Use the zone ranking.' : 'Loading taxi-zone boundaries…'}</p></section>;
  return <Chart title="Taxi-zone demand" subtitle="Weekend / late-night pickups" height={height} headingLevel={3}
    data={[{ type: 'choroplethmap', geojson, featureidkey: 'id', locations: mapped.map(row => row.location_id),
      z: mapped.map(row => number(row.total_filtered_pickups)), text: mapped.map(row => row.zone),
      colorscale, marker: { opacity: .9, line: { width: .35, color: '#fff' } },
      colorbar: { thickness: 8, len: .7, outlinewidth: 0 }, hovertemplate: '%{text}<br>%{z:,.0f} pickups<extra></extra>' }]}
    layout={{ map: { style: 'white-bg', center: { lon: -73.94, lat: 40.72 }, zoom: 9 }, margin: { t: 0, b: 0, l: 0, r: 0 } }}
    note={`${mapped.length} of ${rows.length} groups mapped. Unmatched groups remain in totals and Data. Shading shows volume, not area density.`} />;
}
