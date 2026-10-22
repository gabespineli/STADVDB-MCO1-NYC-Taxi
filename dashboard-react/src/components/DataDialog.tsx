import { useEffect, useRef, useState } from 'react';
import { csv, fmt } from '../analytics';
import type { Report, Row } from '../types';

export default function DataDialog({ reports, current, rows, views, reportIds, onClose }: {
  reports: Record<string, Report>; current: string; rows: Row[] | null; views?: Record<string, Row[]>; reportIds?: string[]; onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [id, setId] = useState(current), [page, setPage] = useState(0);
  const report = reports[id];
  const selected = views?.[id] ?? (id === current && rows !== null ? rows : report.rows);
  const currentView = views?.[id] !== undefined || (id === current && rows !== null);
  useEffect(() => { ref.current?.showModal(); }, []);
  const download = () => {
    const url = URL.createObjectURL(new Blob([csv(selected, report.columns)], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a'); link.href = url; link.download = `${id}_current_view.csv`; link.click();
    URL.revokeObjectURL(url);
  };
  return <dialog className="data-dialog" ref={ref} onClose={onClose} onClick={event => { if (event.target === ref.current) ref.current.close(); }}>
    <div className="dialog-heading"><h2>Data & definitions</h2><button aria-label="Close data" className="icon-button" onClick={() => ref.current?.close()}>×</button></div>
    <label className="dialog-select">Report<select value={id} onChange={event => { setId(event.target.value); setPage(0); }}>
      {(reportIds ?? Object.keys(reports)).map(key => <option key={key} value={key}>{reports[key].title}</option>)}
    </select></label>
    <p>{report.scope}</p><p className="method-note">{report.caution}</p>
    <div className="data-actions"><span>{fmt(selected.length)} rows · {currentView ? 'Current view' : 'Complete output, including rollups'}</span>
      <button onClick={download} disabled={!selected.length}>Download CSV</button></div>
    {!selected.length ? <p className="empty-state">{report.status === 'Ready' ? 'No matching groups.' : report.status}</p> :
      <div className="table-scroll" tabIndex={0} aria-label="Report data"><table><thead><tr>{report.columns.map(key => <th key={key}>{key.replaceAll('_', ' ')}</th>)}</tr></thead>
        <tbody>{selected.slice(page * 100, (page + 1) * 100).map((row, index) => <tr key={index}>{report.columns.map(key =>
          <td key={key} className={typeof row[key] === 'number' ? 'numeric' : ''}>{row[key] === null ? 'NULL' : typeof row[key] === 'number' ? fmt(row[key] as number, Number.isInteger(row[key]) ? 0 : 2) : row[key]}</td>)}</tr>)}</tbody></table></div>}
    {selected.length > 100 && <div className="pagination"><button disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button>
      <span>{page + 1} / {Math.ceil(selected.length / 100)}</span><button disabled={(page + 1) * 100 >= selected.length} onClick={() => setPage(page + 1)}>Next</button></div>}
    <details className="source-details"><summary>Source & complete export</summary>
      {report.source ? <><p>{report.source.filename}</p><p>Exported {report.source.exported_at} · {fmt(report.source.rowCount)} groups</p>
        <a download href={`/data/exports/${report.source.filename}`}>Download original TSV</a><p className="hash">SHA-256 {report.source.sha256}</p></> : <p>{report.status}</p>}
      <p>CSV preserves SQL NULL as \N and literal N/A labels. Charts exclude subtotal rows. Chart-local selections may display subsets of the current table. Counts across reports overlap and must not be added.</p>
    </details>
  </dialog>;
}
