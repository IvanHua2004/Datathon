import { Duel } from '../models/duel.model';

/** Le dernier duel jugé, pour que le tableau de bord comparatif le relise sans relancer Bedrock. */
const CLE = 'rdc-dernier-duel';

export function cleDuel(profil: string, a: string, b: string): string {
  return `${profil}|${a}|${b}`;
}

export function memoriserDuel(cle: string, duel: Duel): void {
  try {
    sessionStorage.setItem(CLE, JSON.stringify({ cle, duel }));
  } catch {
    // Stockage indisponible (navigation privée stricte) : le tableau de bord se passera de la décision.
  }
}

export function relireDuel(cle: string): Duel | null {
  try {
    const brut = sessionStorage.getItem(CLE);
    if (!brut) return null;
    const lu = JSON.parse(brut) as { cle: string; duel: Duel };
    return lu.cle === cle ? lu.duel : null;
  } catch {
    return null;
  }
}
