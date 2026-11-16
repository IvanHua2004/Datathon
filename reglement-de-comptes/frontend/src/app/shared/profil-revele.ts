import { Profil } from '../models/proces.model';
import { tonVerdict } from './format';
import { VoteEnregistre } from './memoire';

/**
 * Le profil d'investisseur « d'après vos choix » : chaque vote de la session dit si l'investisseur
 * a pris plus de risque, autant, ou moins que son profil déclaré. La règle est fixe et expliquée
 * ligne par ligne ; ce n'est pas une évaluation réglementaire, seulement un miroir pédagogique.
 */

/** Les cinq niveaux de risque des personas, avec leur budget de perte de référence. */
export const NIVEAUX = [
  { cle: 'faible', libelle: 'Faible', budget: 0.08 },
  { cle: 'faible_a_modere', libelle: 'Faible à modéré', budget: 0.12 },
  { cle: 'modere', libelle: 'Modéré', budget: 0.25 },
  { cle: 'modere_a_eleve', libelle: 'Modéré à élevé', budget: 0.35 },
  { cle: 'eleve', libelle: 'Élevé', budget: 0.45 },
] as const;

/** +1 : plus de risque que le profil ; 0 : aligné ; −1 : plus prudent. */
export type Signal = -1 | -0.5 | 0 | 1 | 2;

export interface Indice {
  vote: VoteEnregistre;
  signal: Signal;
  explication: string;
  /** Faux quand le vote ne dit rien du rapport au risque (verdict indécidable, duel non départagé). */
  compte: boolean;
}

export interface ProfilRevele {
  declare: number;      // index dans NIVEAUX
  revele: number;       // index dans NIVEAUX
  ecart: -1 | 0 | 1;    // plus prudent, aligné, plus audacieux
  moyenne: number;
  indices: Indice[];
  fiabilite: 'aucune' | 'faible' | 'indicative' | 'solide';
}

export function niveauDeclare(profil: Profil): number {
  const budget = Math.abs(profil.budgetPerte);
  let meilleur = 0;
  NIVEAUX.forEach((n, i) => {
    if (Math.abs(n.budget - budget) < Math.abs(NIVEAUX[meilleur].budget - budget)) meilleur = i;
  });
  return meilleur;
}

function lire(v: VoteEnregistre): Indice {
  if (v.type === 'duel') {
    const choisi = v.vote;
    if (!v.gagnant || v.plusRisque == null) {
      return { vote: v, signal: 0, explication: `Vous avez choisi ${choisi} ; le tribunal ne départage pas, aucun indice.`, compte: false };
    }
    if (v.gagnant === choisi) {
      return { vote: v, signal: 0, explication: `Vous avez choisi ${choisi}, le titre que votre profil retient aussi.`, compte: true };
    }
    return v.plusRisque
      ? { vote: v, signal: 1, explication: `Vous avez préféré ${choisi}, le plus risqué des deux, alors que votre profil retient ${v.gagnant}.`, compte: true }
      : { vote: v, signal: -1, explication: `Vous avez préféré ${choisi}, le plus prudent des deux, alors que votre profil accepte ${v.gagnant}.`, compte: true };
  }
  const ton = v.verdictTribunal ? tonVerdict(v.verdictTribunal) : 'indecidable';
  const pour = v.vote === 'avocat_defense';
  const titre = `${v.ticker} à ${Math.round(v.taille * 100)} %`;
  if (ton === 'indecidable') {
    return { vote: v, signal: 0, explication: `${titre} : verdict indécidable, aucun indice.`, compte: false };
  }
  if (pour) {
    if (ton === 'contraire') return { vote: v, signal: 2, explication: `${titre} : vous défendiez un ajout que votre profil refuse.`, compte: true };
    if (ton === 'tension') return { vote: v, signal: 1, explication: `${titre} : vous défendiez un ajout en tension avec votre profil.`, compte: true };
    return { vote: v, signal: 0, explication: `${titre} : vous défendiez un ajout compatible avec votre profil.`, compte: true };
  }
  if (ton === 'compatible') return { vote: v, signal: -1, explication: `${titre} : vous refusiez un ajout que votre profil accepte.`, compte: true };
  if (ton === 'tension') return { vote: v, signal: -0.5, explication: `${titre} : vous refusiez un ajout en tension, par prudence.`, compte: true };
  return { vote: v, signal: 0, explication: `${titre} : vous refusiez un ajout que votre profil refuse aussi.`, compte: true };
}

export function profilRevele(profil: Profil, votes: readonly VoteEnregistre[]): ProfilRevele {
  const declare = niveauDeclare(profil);
  const indices = votes.map(lire);
  const comptes = indices.filter((i) => i.compte);
  const moyenne = comptes.length ? comptes.reduce((s, i) => s + i.signal, 0) / comptes.length : 0;
  const decalage = Math.abs(moyenne) < 0.34 ? 0 : Math.sign(moyenne) * Math.max(1, Math.round(Math.abs(moyenne)));
  const revele = Math.min(NIVEAUX.length - 1, Math.max(0, declare + decalage));
  const n = comptes.length;
  return {
    declare,
    revele,
    ecart: revele > declare ? 1 : revele < declare ? -1 : 0,
    moyenne,
    indices,
    fiabilite: n === 0 ? 'aucune' : n === 1 ? 'faible' : n < 4 ? 'indicative' : 'solide',
  };
}
