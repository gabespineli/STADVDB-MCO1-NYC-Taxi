import type { ComponentProps, ReactNode } from 'react';
import Chart from './Chart';
import { questions, type QuestionId } from '../questions';
import type { Snapshot } from '../types';

export function QuestionFrame({ id, snapshot, children }: { id: QuestionId; snapshot: Snapshot; children: ReactNode }) {
  const question = questions.find(question => question.id === id)!;
  const unavailable = question.reports.filter(id => snapshot.reports[id].status !== 'Ready');
  return <section id={id} className="question-board" aria-labelledby={`${id}-question`}>
    <header className="question-heading"><span className="question-number">{question.number}</span><h2 id={`${id}-question`}>{question.title}</h2></header>
    {unavailable.length > 0 && <p className="availability-note" role="status">{unavailable.length} supporting exports unavailable. Open Data for details.</p>}
    <div className={`bento-grid bento-${id}`}>{children}</div>
  </section>;
}
export function BentoChart({ area, ...props }: ComponentProps<typeof Chart> & { area: string }) {
  return <div className={`bento-cell cell-${area}`}><Chart {...props} headingLevel={3} /></div>;
}
export function AnswerTile({ area = 'answer', label, value, unit, detail, context }: {
  area?: string; label: string; value: string; unit?: string; detail: string; context?: string;
}) {
  return <section className={`bento-answer bento-cell cell-${area}`}>
    <h3>{label}</h3><p className="answer-value">{value}<small>{unit}</small></p><p className="answer-detail">{detail}</p>
    {context && <p className="answer-context">{context}</p>}
  </section>;
}
