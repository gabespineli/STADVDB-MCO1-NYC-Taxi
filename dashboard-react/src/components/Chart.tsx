import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { PlotElement, Trace, PlotLayout } from '../types';
import { palette, selectionValue } from '../analytics';
import { plotlyReady } from '../plotly-runtime';

interface Props {
  title: string; subtitle?: string; data: Trace[]; layout?: PlotLayout;
  height?: number; note?: string; controls?: ReactNode; onSelect?: (value: string) => void;
  headingLevel?: 2 | 3;
}

export default function Chart({ title, subtitle, data, layout = {}, height = 320, note, controls, onSelect, headingLevel = 2 }: Props) {
  const Heading = headingLevel === 3 ? 'h3' : 'h2';
  const ref = useRef<PlotElement>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    let active = true;
    setError('');
    const chartLayout: PlotLayout = {
      autosize: true, height, paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
      font: { family: 'Arial, sans-serif', size: 12, color: '#536474' }, colorway: palette,
      margin: { t: 16, r: 20, b: 40, l: 48 }, hovermode: 'closest',
      xaxis: { gridcolor: '#e9edf0', zeroline: false, automargin: true, fixedrange: true },
      yaxis: { gridcolor: '#e9edf0', zeroline: false, automargin: true, fixedrange: true },
      legend: { orientation: 'h', y: 1.12, x: 0, font: { size: 11 } },
      ...layout,
    };
    plotlyReady().then(() => active ? window.Plotly.react(element, data, chartLayout, { displayModeBar: false, responsive: true, displaylogo: false, scrollZoom: false }) : undefined)
      .then(() => {
        if (!active) return;
        element.removeAllListeners?.('plotly_click');
        if (onSelect) element.on?.('plotly_click', event => {
          const value = selectionValue(event.points[0]?.customdata);
          if (value !== undefined) onSelect(value);
        });
      }).catch(() => { if (active) setError('This chart could not be rendered. The source table is available in Data.'); });
    const observer = new ResizeObserver(() => {
      if (element.isConnected && element.childElementCount && window.Plotly) window.Plotly.Plots.resize(element);
    });
    observer.observe(element);
    return () => { active = false; observer.disconnect(); };
  }, [data, layout, height, onSelect]);
  useEffect(() => {
    const element = ref.current;
    return () => { if (element && window.Plotly) window.Plotly.purge(element); };
  }, []);
  return <section className="chart-panel">
    <div className="chart-heading"><div><Heading>{title}</Heading>{subtitle && <p>{subtitle}</p>}</div>{controls}</div>
    {error ? <p role="alert" className="empty-state">{error}</p> :
      <div ref={ref} className="plot" style={{ minHeight: height }} role="img" aria-label={`${title}. Exact values are available in Data.`} />}
    {note && <p className="chart-note">{note}</p>}
  </section>;
}

export function Metric({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return <div className="metric"><span>{label}</span><strong>{value}<small>{unit}</small></strong></div>;
}

export function Select({ label, value, options, onChange }: { label: string; value: string; options: (string | { value: string; label: string })[]; onChange: (value: string) => void }) {
  return <label className="select-control"><span>{label}</span><select value={value} onChange={event => onChange(event.target.value)}>
    {options.map(option => typeof option === 'string' ? <option key={option}>{option}</option> :
      <option key={option.value} value={option.value}>{option.label}</option>)}
  </select></label>;
}
