import type { Row } from './types.ts';

export type QuestionId = 'demand' | 'payments' | 'travel';
export type ViewedRows = Record<string, Row[]>;
export const questions: { id: QuestionId; number: string; label: string; title: string; reports: string[] }[] = [
  { id: 'demand', number: 'Q1', label: 'Demand', title: 'Where and when is taxi demand strongest?', reports: ['q1_demand', 'q1_hourly', 'q1_monthly'] },
  { id: 'payments', number: 'Q2', label: 'Payments', title: 'How do payments vary by fare, place, and time?', reports: ['q2_fare', 'q2_payment'] },
  { id: 'travel', number: 'Q3', label: 'Travel', title: 'Where does rush-hour travel take longer?', reports: ['q3_comparison', 'q3_location'] },
];
export function questionFromHash(hash: string): QuestionId {
  const path = hash.replace(/^#\/?/, '');
  if (path === 'payments' || path.startsWith('q2_')) return 'payments';
  if (path === 'travel' || path.startsWith('q3_')) return 'travel';
  return 'demand';
}
