let ready: Promise<void> | null = null;
export function plotlyReady(): Promise<void> {
  if (window.Plotly) return Promise.resolve();
  if (!ready) ready = new Promise((resolve, reject) => {
    const script = document.getElementById('plotly-runtime');
    if (!script || document.readyState === 'complete') { reject(new Error('Plotly is unavailable')); return; }
    script.addEventListener('load', () => window.Plotly ? resolve() : reject(new Error('Plotly is unavailable')), { once: true });
    script.addEventListener('error', () => reject(new Error('Plotly is unavailable')), { once: true });
  });
  return ready;
}
