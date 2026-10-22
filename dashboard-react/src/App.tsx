import { Component, useEffect, useRef, useState, type ReactNode } from 'react';
import Overview from './views/Overview';
import ReportPage from './views/ReportPage';
import DataDialog from './components/DataDialog';
import { detail } from './analytics';
import type { Row, Section, Snapshot } from './types';

const sections: { id: Section; title: string; first: string; query: string }[] = [
  { id: 'overview', title: 'Overview', first: 'overview', query: '' },
  { id: 'demand', title: 'Demand', first: 'q1_demand', query: 'Q1' },
  { id: 'payments', title: 'Payments', first: 'q2_fare', query: 'Q2' },
  { id: 'travel', title: 'Travel', first: 'q3_comparison', query: 'Q3' },
];
const reportLabels: Record<string, string> = {
  q1_demand: 'Zones & boroughs', q1_hourly: 'Hourly patterns', q1_monthly: 'Monthly consistency',
  q2_fare: 'Fare ranges', q2_payment: 'Borough & time', q3_comparison: 'Rush hour & off-peak', q3_location: 'Location profiles',
};
function route() { return window.location.hash.replace(/^#\/?/, '') || 'overview'; }

class ViewBoundary extends Component<{ children: ReactNode }, { error: boolean }> {
  state = { error: false };
  static getDerivedStateFromError() { return { error: true }; }
  render() { return this.state.error ? <div role="alert" className="empty-state"><h2>This view could not be displayed</h2>
    <p>Open Data to inspect the source groups, or select another report.</p></div> : this.props.children; }
}

export default function App() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null), [error, setError] = useState('');
  const [id, setId] = useState(route), [menuOpen, setMenuOpen] = useState(false), [dataOpen, setDataOpen] = useState(false);
  const [currentRows, setCurrentRows] = useState<Row[] | null>(null), [retracted, setRetracted] = useState(false);
  const mobileMenu = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    fetch('/data/snapshot.json', { signal: controller.signal }).then(response => {
      if (!response.ok) throw new Error('Saved results could not load. Run npm run data, then reload.'); return response.json();
    }).then(value => {
      if (!value.reports || !value.period) throw new Error('The saved snapshot is invalid. Run npm run data again.');
      setSnapshot(value);
    }).catch(error => { if (error.name !== 'AbortError') setError(error.message); });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    const change = () => { setId(route()); setMenuOpen(false); setDataOpen(false); setCurrentRows(null); setRetracted(false); window.scrollTo({ top: 0 }); };
    window.addEventListener('hashchange', change); return () => window.removeEventListener('hashchange', change);
  }, []);
  useEffect(() => {
    let last = window.scrollY;
    const scroll = () => { const current = window.scrollY; if (Math.abs(current - last) > 8) { setRetracted(current > 130 && current > last); last = current; } };
    window.addEventListener('scroll', scroll, { passive: true }); return () => window.removeEventListener('scroll', scroll);
  }, []);
  useEffect(() => {
    if (!menuOpen) return;
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') { setMenuOpen(false); document.getElementById('menu-toggle')?.focus(); } };
    const outside = (event: PointerEvent) => { if (!mobileMenu.current?.contains(event.target as Node)) setMenuOpen(false); };
    window.addEventListener('keydown', close); window.addEventListener('pointerdown', outside);
    return () => { window.removeEventListener('keydown', close); window.removeEventListener('pointerdown', outside); };
  }, [menuOpen]);
  const report = snapshot?.reports[id];
  const activeSection = id === 'overview' ? sections[0] : sections.find(section => section.query === report?.section) ?? sections[0];
  const activeReports = snapshot ? Object.values(snapshot.reports).filter(item => item.section === activeSection.query) : [];
  const validRoute = id === 'overview' || Boolean(report);
  return <>
    <a className="skip-link" href="#main-content" onClick={event => { event.preventDefault(); document.getElementById('main-content')?.focus(); }}>Skip to data</a>
    <header className={`topbar ${retracted && !menuOpen ? 'is-retracted' : ''}`}>
      <div className="nav-inner" ref={mobileMenu}>
        <a className="brand" href="#/overview"><img src="/taxi.svg" alt="" width="28" height="28" /><strong>NYC Taxi</strong><span>2025</span></a>
        <button id="menu-toggle" className="mobile-toggle" aria-label="Queries" aria-expanded={menuOpen} aria-controls="primary-nav" onClick={() => setMenuOpen(!menuOpen)}>Queries <span aria-hidden="true">⌄</span></button>
        <nav id="primary-nav" aria-label="Queries" className={menuOpen ? 'primary-nav is-open' : 'primary-nav'}>
          {sections.map(section => <a key={section.id} href={`#/${section.first}`} aria-current={activeSection.id === section.id ? 'page' : undefined}>
            {section.query && <small>{section.query}</small>}{section.title}</a>)}
        </nav>
        <span className="snapshot-tag"><i />Saved exports</span>
      </div>
    </header>
    <main id="main-content" tabIndex={-1}>
      <div className="page-heading"><div><h1>{id === 'overview' ? 'Overview' : report?.title ?? 'Report unavailable'}</h1><p>January–December 2025</p></div>
        <button className="data-button" onClick={() => setDataOpen(true)} disabled={!snapshot}>Data <span aria-hidden="true">↗</span></button></div>
      {activeReports.length > 0 && <nav className="report-nav" aria-label={`${activeSection.title} reports`}>
        {activeReports.map(item => <a key={item.id} href={`#/${item.id}`} aria-current={item.id === id ? 'page' : undefined}>{reportLabels[item.id]}</a>)}
      </nav>}
      {error ? <div role="alert" className="empty-state"><h2>Results unavailable</h2><p>{error}</p><button onClick={() => window.location.reload()}>Reload</button></div> :
        !snapshot ? <div className="loading-state" aria-busy="true" aria-label="Loading saved results"><div /><div /><div /></div> :
        !validRoute ? <div role="status" className="empty-state"><p>This report does not exist.</p><a href="#/overview">Open Overview</a></div> :
        <ViewBoundary key={id}>{id === 'overview' ? <Overview snapshot={snapshot} /> :
          <ReportPage key={id} report={report!} mapAvailable={snapshot.mapAvailable} onRowsChange={setCurrentRows} />}</ViewBoundary>}
      <footer><span>NYC yellow taxi · 2025 query results</span><span>Completed exports · {snapshot ? `${Object.values(snapshot.reports).filter(report => report.status === 'Ready').length}/7 reports` : '…'}</span></footer>
    </main>
    {dataOpen && snapshot && <DataDialog reports={snapshot.reports} current={report ? id : 'q1_demand'}
      rows={id === 'overview' ? null : currentRows ?? detail(report?.rows ?? [])} onClose={() => setDataOpen(false)} />}
  </>;
}
