/** Mise en forme identique à celle du greffier Python (backend/rdc/format.py). */

export function pct(x: number, decimales = 1): string {
  return `${(x * 100).toFixed(decimales).replace('.', ',')} %`;
}

export function dollars(x: number): string {
  const arrondi = Math.round(x / 100) * 100;
  const signe = arrondi < 0 ? '-' : '';
  const chiffres = Math.abs(arrondi).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  return `${signe}${chiffres} $`;
}

export type TonVerdict = 'contraire' | 'tension' | 'indecidable' | 'compatible';

export function tonVerdict(verdict: string): TonVerdict {
  if (verdict.startsWith('Contraire')) return 'contraire';
  if (verdict.startsWith('En tension')) return 'tension';
  if (verdict.startsWith('Indécidable')) return 'indecidable';
  return 'compatible';
}
