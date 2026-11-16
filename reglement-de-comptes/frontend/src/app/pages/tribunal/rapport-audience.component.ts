import { Component, computed, input } from '@angular/core';

import { CourbeTailleComponent } from '../../components/courbe-taille/courbe-taille.component';
import { Piece, PointCourbe, Position, Proces, TourDiscussion } from '../../models/proces.model';
import { dollars, pct, tonVerdict } from '../../shared/format';

type Camp = 'avocat_defense' | 'procureur';

export interface InterventionLue {
  tour: TourDiscussion;
  extrait: string;
  complet: boolean;
}

const PHRASES = new Intl.Segmenter('fr', { granularity: 'sentence' });

/**
 * Les phrases d'une plaidoirie qui portent un argument : celles qui citent un chiffre ou
 * une pièce passent avant les formules d'audience (« Monsieur le Président… »).
 * Le texte n'est pas réécrit, seulement sélectionné, dans l'ordre d'origine.
 */
export function argumentsDe(texte: string, n: number): string[] {
  const phrases = Array.from(PHRASES.segment(texte)).map(({ segment }) => segment.trim()).filter((s) => s.length > 25);
  const fortes = phrases.filter((s) => /\d|\[P-\d+\]/.test(s));
  const choisies = new Set((fortes.length >= n ? fortes : [...fortes, ...phrases.filter((s) => !fortes.includes(s))]).slice(0, n));
  return phrases.filter((s) => choisies.has(s));
}

/** Pire baisse, part du risque… avant et après la demande, lus sur la courbe du procès. */
export function chiffresCles(pr: Proces | null) {
  if (!pr?.courbe.length) return null;
  const avant = pointPour(pr.courbe, 0)!;
  const apres = pointPour(pr.courbe, pr.demande.taille)!;
  // budgetPerte arrive déjà en négatif depuis l'API (ex. -0,12).
  return { avant, apres, depasse: apres.pireBaisse < pr.budgetPerte };
}

/** Le point de la courbe le plus proche d'une part donnée. */
function pointPour(courbe: readonly PointCourbe[], taille: number): PointCourbe | undefined {
  return [...courbe].sort((a, b) => Math.abs(a.taille - taille) - Math.abs(b.taille - taille))[0];
}

/**
 * Le rapport d'analyse de l'audience, organisé autour des 4 questions d'une explication
 * crédible : quelle conclusion et pourquoi, sur quelles données, avec quelles limites,
 * et qu'est-ce qui changerait la réponse. Tout vient de la réponse de l'API : aucun chiffre
 * n'est recalculé ici, sauf le portefeuille après ajout (simple règle de trois).
 */
@Component({
  selector: 'rdc-rapport-audience',
  imports: [CourbeTailleComponent],
  templateUrl: './rapport-audience.component.html',
  styleUrl: './rapport-audience.component.scss',
})
export class RapportAudienceComponent {
  readonly proces = input<Proces | null>(null);
  readonly interventions = input<readonly InterventionLue[]>([]);
  readonly pieces = input<readonly Piece[]>([]);
  readonly vote = input<Camp | null>(null);
  readonly audienceTerminee = input(false);
  /** Affiché à côté du vote : inutile de rappeler comment voter. */
  readonly pendantLeVote = input(false);
  /** Rapport relu après coup (tableau de bord) : pas d'invitation à voter. */
  readonly horsAudience = input(false);
  /** Avant le vote de l'investisseur : la décision du tribunal reste scellée. */
  readonly masquerDecision = input(false);
  readonly portefeuille = input<readonly Position[]>([]);

  readonly pct = pct;
  readonly dollars = dollars;
  readonly tonVerdict = tonVerdict;

  readonly ton = computed(() => tonVerdict(this.proces()?.decision.verdict ?? ''));

  readonly motifs = computed(() => {
    const d = this.proces()?.decision;
    return d ? [...d.contraintes, ...d.tensions, ...d.manquants].map((m) => m.texte) : [];
  });

  /** Le tribunal donne raison à la défense si le verdict est compatible, à l'accusation sinon. */
  readonly accord = computed<boolean | null>(() => {
    const v = this.vote();
    const ton = this.ton();
    if (!v || ton === 'indecidable') return null;
    const tribunalPour = ton === 'compatible';
    return (v === 'avocat_defense') === tribunalPour;
  });

  readonly chiffres = computed(() => chiffresCles(this.proces()));

  readonly portefeuilles = computed(() => {
    const pr = this.proces();
    const actuel = this.portefeuille();
    if (!pr || !actuel.length) return null;
    const t = pr.demande.taille;
    const apres = actuel.map((x) => ({ ticker: x.ticker, poids: x.poids * (1 - t) }));
    const existant = apres.find((x) => x.ticker === pr.demande.ticker);
    if (existant) existant.poids += t;
    else apres.push({ ticker: pr.demande.ticker, poids: t });
    const decrire = (p: { ticker: string; poids: number }[]) =>
      p.map((x) => `${x.ticker} ${pct(x.poids, 0)}`).join(', ');
    return [
      { nom: 'Avant', positions: actuel, description: `Portefeuille avant : ${decrire([...actuel])}` },
      { nom: 'Après', positions: apres, description: `Portefeuille après : ${decrire(apres)}` },
    ];
  });

  readonly camps = computed(() => {
    const pl = this.proces()?.plaidoiries ?? [];
    return [
      { cle: 'defense', titre: 'La Défense · pour la demande', p: pl[0] },
      { cle: 'accusation', titre: 'L’accusation · contre la demande', p: pl[1] },
    ].map(({ cle, titre, p }) => ({
      cle,
      titre,
      arguments: p ? argumentsDe(p.texte, 3) : ['Plaidoirie indisponible.'],
      nonVerifies: p?.non_verifies ?? [],
    }));
  });

}
