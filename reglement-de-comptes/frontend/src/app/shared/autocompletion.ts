import { Actif } from '../models/proces.model';

/**
 * Suggestions pour compléter la phrase pendant qu'on répond au greffier.
 * Tout se passe dans le navigateur, sans appel réseau : la grammaire visée est
 * « [début] [part] % de mon portefeuille dans [titre] ? ».
 */

/** Ce que le greffier attend après sa dernière réponse. */
export type Attente = 'part' | 'titre' | null;

export interface ContexteCompletion {
  actifs: Actif[];
  attente: Attente;
  /** Titre proposé en premier quand rien n'est encore tapé (l'exemple du persona). */
  exemple: string;
}

const DEBUTS = ['Devrais-je placer', 'Est-ce raisonnable de placer', 'Et si je plaçais'];
const PARTS = [5, 10, 15, 20, 25, 30, 40, 50];
const POPULAIRES = ['SPY', 'XIU.TO', 'NVDA', 'GLD', 'XBB.TO', 'BTC-USD', 'AAPL'];
const VERBES = /\b(placer|plaçais|placais|mettre|mettais|investir|investissais|ajouter|ajoutais|allouer)\s*$/i;
const MAX = 5;

export function normaliser(texte: string): string {
  return texte
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/’/g, "'")
    .toLowerCase();
}

export function libelle(actif: Actif): string {
  return `${actif.nom} (${actif.ticker})`;
}

/** Le titre nommé dans le texte, s'il y en a un. */
export function actifNomme(texte: string, actifs: Actif[]): Actif | null {
  const t = normaliser(texte);
  for (const a of actifs) {
    const symbole = normaliser(a.ticker);
    const base = symbole.split(/[.-]/)[0];
    const nom = normaliser(a.nom).replace(/\s*\(.*\)$/, '');
    const motif = (m: string) => new RegExp(`(^|[^\\w&])${echapper(m)}($|[^\\w&])`).test(t);
    if (motif(nom) || motif(symbole) || (base.length > 2 && motif(base))) return a;
  }
  return null;
}

function echapper(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function trier(actifs: Actif[], exemple: string): Actif[] {
  const rang = (a: Actif) => {
    if (a.ticker === exemple) return -1;
    const i = POPULAIRES.indexOf(a.ticker);
    return i === -1 ? 100 : i;
  };
  return [...actifs].sort((a, b) => rang(a) - rang(b));
}

/** Titres dont le nom ou le symbole commence par le fragment tapé. */
function titresPour(fragment: string, ctx: ContexteCompletion): Actif[] {
  const f = normaliser(fragment).replace(/^(l'|le |la |les |du |de la |de l'|des )/, '').trim();
  const tries = trier(ctx.actifs, ctx.exemple);
  if (!f) return tries;
  return tries.filter((a) => {
    const mots = normaliser(a.nom).split(/[\s(&-]+/);
    return normaliser(a.ticker).startsWith(f) || normaliser(a.nom).startsWith(f) || mots.some((m) => m.startsWith(f));
  });
}

function uniques(liste: string[], texte: string): string[] {
  const vus = new Set<string>();
  return liste
    .filter((s) => s.trim() !== texte.trim() && !vus.has(s) && vus.add(s))
    .slice(0, MAX);
}

export function completer(texte: string, ctx: ContexteCompletion): string[] {
  const brut = texte.replace(/\s+$/, '');
  const t = normaliser(brut);
  const actif = actifNomme(brut, ctx.actifs);
  const aPart = /\d\s*(%|pour ?cent)/.test(t);

  // Rien de tapé : on propose de quoi commencer, selon ce que le greffier attend.
  if (!t) {
    if (ctx.attente === 'part') return PARTS.slice(0, 5).map((p) => `${p} %`);
    if (ctx.attente === 'titre') return titresPour('', ctx).slice(0, MAX).map((a) => `Dans ${libelle(a)}`);
    return DEBUTS.map((d) => `${d} `);
  }

  // Le greffier attend la part et on tape un nombre.
  const nombre = brut.match(/(\d{1,2})$/);
  if (nombre && !aPart) {
    const avant = brut.slice(0, nombre.index);
    const fin = actif || ctx.attente === 'part' ? (ctx.attente === 'part' && !avant.trim() ? '' : ' ?') : ' de mon portefeuille dans ';
    return uniques(
      PARTS.filter((p) => String(p).startsWith(nombre[1])).map((p) => `${avant}${p} %${fin}`),
      brut,
    );
  }

  // Début de phrase.
  if (!aPart && !actif) {
    const debuts = DEBUTS.filter((d) => normaliser(d).startsWith(t) && normaliser(d) !== t);
    if (debuts.length) return debuts.map((d) => `${d} `);
    if (VERBES.test(brut)) {
      return [10, 5, 20].map((p) => `${brut} ${p} % de mon portefeuille dans `);
    }
  }

  // La part est là, il manque le titre : on complète le dernier mot avec les 31 actifs.
  if (aPart && !actif) {
    const apresPart = brut.slice(brut.search(/\d+\s*(%|pour ?cent)/i));
    const dans = apresPart.match(/^(.*?\b(?:dans|en|sur|de|du)\s+)((?:l'|le |la |les )?[^\s?]*)$/i);
    if (dans && !/portefeuille\s*$/i.test(dans[1] + dans[2])) {
      const prefixe = brut.slice(0, brut.length - dans[2].length);
      return uniques(titresPour(dans[2], ctx).map((a) => `${prefixe}${libelle(a)} ?`), brut);
    }
    const suite = /portefeuille$/i.test(brut) ? ' dans ' : ' de mon portefeuille dans ';
    return uniques(
      titresPour('', ctx).slice(0, 3).map((a) => `${brut}${suite}${libelle(a)} ?`),
      brut,
    );
  }

  // Titre et part présents : il ne manque que le point d'interrogation.
  if (actif && aPart && !brut.endsWith('?')) return [`${brut} ?`];

  // Titre en cours de frappe sans part (« Que penses-tu de Shop… »).
  const dernier = brut.match(/(?:^|\s)([^\s]{3,})$/);
  if (!actif && dernier) {
    const prefixe = brut.slice(0, brut.length - dernier[1].length);
    return uniques(titresPour(dernier[1], ctx).slice(0, MAX).map((a) => `${prefixe}${libelle(a)}`), brut);
  }
  return [];
}
