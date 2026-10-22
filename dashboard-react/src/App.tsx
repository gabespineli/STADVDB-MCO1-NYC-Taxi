import { Component, useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import DemandBoard from './questions/DemandBoard';
import PaymentsBoard from './questions/PaymentsBoard';
import TravelBoard from './questions/TravelBoard';
import DataDialog from './components/DataDialog';
import { questions, questionFromHash, type QuestionId, type ViewedRows } from './questions';
import type { Snapshot } from './types';
import './bento.css';

class ViewBoundary extends Component<{ children: ReactNode }, { error: boolean }> {
  state = { error: false };
  static getDerivedStateFromError() { return { error: true }; }
  render() { return this.state.error ? <div role="alert" className="empty-state"><h2>This question could not be displayed</h2>
    <p>Open Data to inspect the saved results.</p></div> : this.props.children; }
}

export default function App() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null), [error, setError] = useState('');
  const [active, setActive] = useState<QuestionId>(() => questionFromHash(window.location.hash));
  const [menuOpen, setMenuOpen] = useState(false), [dataQuestion, setDataQuestion] = useState<QuestionId | null>(null);
  const [views, setViews] = useState<ViewedRows>({}), [retracted, setRetracted] = useState(false);
  const mobileMenu = useRef<HTMLDivElement>(null);
  const onViewsChange = useCallback((rows: ViewedRows) => setViews(previous => ({ ...previous, ...rows })), []);
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
    if (!snapshot) return;
    const move = () => {
      const question = questionFromHash(window.location.hash);
      setActive(question); setMenuOpen(false); setDataQuestion(null); setRetracted(false);
      document.getElementById(question)?.scrollIntoView({ block: 'start' });
    };
    move();
    window.addEventListener('hashchange', move);
    return () => window.removeEventListener('hashchange', move);
  }, [snapshot]);
  useEffect(() => {
    if (!snapshot) return;
    const nodes = questions.map(question => document.getElementById(question.id)).filter((node): node is HTMLElement => node !== null);
    const observer = new IntersectionObserver(entries => {
      const entering = entries.filter(entry => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (entering) setActive(entering.target.id as QuestionId);
    }, { rootMargin: '-80px 0px -65% 0px', threshold: 0 });
    nodes.forEach(node => observer.observe(node));
    return () => observer.disconnect();
  }, [snapshot]);
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
  const dataIds = questions.find(question => question.id === dataQuestion)?.reports;
  return <>
    <a className="skip-link" href="#main-content" onClick={event => { event.preventDefault(); document.getElementById('main-content')?.focus(); }}>Skip to data</a>
    <header className={`topbar ${retracted && !menuOpen ? 'is-retracted' : ''}`}>
      <div className="nav-inner" ref={mobileMenu}>
        <a className="brand" href="#/demand"><img src="/taxi.svg" alt="" width="28" height="28" /><strong>NYC Taxi</strong><span>2025</span></a>
        <button id="menu-toggle" className="mobile-toggle" aria-label="Questions" aria-expanded={menuOpen} aria-controls="primary-nav" onClick={() => setMenuOpen(!menuOpen)}>Questions <span aria-hidden="true">⌄</span></button>
        <nav id="primary-nav" aria-label="Questions" className={menuOpen ? 'primary-nav is-open' : 'primary-nav'}>
          {questions.map(question => <a key={question.id} href={`#/${question.id}`} aria-current={active === question.id ? 'location' : undefined}>
            <small>{question.number}</small>{question.label}</a>)}
        </nav>
        <button className="data-button nav-data" onClick={() => setDataQuestion(active)} disabled={!snapshot} aria-label={`Data for ${active}`}>Data <span aria-hidden="true">↗</span></button>
      </div>
    </header>
    <main id="main-content" className="bento-page" tabIndex={-1}>
      <h1 className="visually-hidden">2025 NYC taxi demand, payments, and travel</h1>
      {error ? <div role="alert" className="empty-state"><h2>Results unavailable</h2><p>{error}</p><button onClick={() => window.location.reload()}>Reload</button></div> :
        !snapshot ? <div className="loading-state" aria-busy="true" aria-label="Loading saved results"><div /><div /><div /></div> : <>
          <ViewBoundary><DemandBoard snapshot={snapshot} onViewsChange={onViewsChange} /></ViewBoundary>
          <ViewBoundary><PaymentsBoard snapshot={snapshot} onViewsChange={onViewsChange} /></ViewBoundary>
          <ViewBoundary><TravelBoard snapshot={snapshot} onViewsChange={onViewsChange} /></ViewBoundary>
        </>}
      <footer><span>January–December 2025 · NYC yellow taxi</span><span>Saved exports · {snapshot ? `${Object.values(snapshot.reports).filter(report => report.status === 'Ready').length}/7 reports` : '…'}</span></footer>
    </main>
    {dataQuestion && snapshot && dataIds && <DataDialog reports={snapshot.reports} current={dataIds[0]} rows={null} views={views} reportIds={dataIds} onClose={() => setDataQuestion(null)} />}
  </>;
}
