export type Cell = string | number | null;
export type Row = Record<string, Cell>;
export type Section = 'overview' | 'demand' | 'payments' | 'travel';
export interface Report {
  id: string;
  section: string;
  title: string;
  scope: string;
  caution: string;
  columns: string[];
  rows: Row[];
  mapRows?: Row[];
  status: string;
  source: { filename: string; exported_at: string; sha256: string; rowCount: number } | null;
}
export interface Snapshot { generatedAt: string; period: string; reports: Record<string, Report>; mapAvailable: boolean }
export interface Trace { type: string; [key: string]: unknown }
export interface PlotLayout { [key: string]: unknown }
export interface PlotEvent { points: { customdata?: unknown; x?: unknown; y?: unknown }[] }
export interface PlotElement extends HTMLDivElement { on?: (event: string, callback: (event: PlotEvent) => void) => void; removeAllListeners?: (event: string) => void }
declare global {
  interface Window {
    Plotly: {
      react: (element: HTMLElement, data: Trace[], layout: PlotLayout, config: Record<string, unknown>) => Promise<unknown>;
      purge: (element: HTMLElement) => void;
      Plots: { resize: (element: HTMLElement) => void };
    };
  }
}
