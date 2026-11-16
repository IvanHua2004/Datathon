/**
 * Petite mémoire de session (sessionStorage) : la conversation survit à un aller-retour
 * vers le tribunal ou le duel. Elle s'efface à la fermeture de l'onglet. Le stockage peut
 * être indisponible (navigation privée, iframe) : on l'entoure de try/catch.
 */
export function lire<T>(cle: string): T | null {
  try {
    const brut = sessionStorage.getItem(cle);
    return brut ? (JSON.parse(brut) as T) : null;
  } catch {
    return null;
  }
}

export function ecrire(cle: string, valeur: unknown): void {
  try {
    sessionStorage.setItem(cle, JSON.stringify(valeur));
  } catch {
    /* stockage indisponible : la conversation ne sera simplement pas gardée */
  }
}

export function effacer(cle: string): void {
  try {
    sessionStorage.removeItem(cle);
  } catch {
    /* rien à faire */
  }
}

export const cleConversation = (profil: string) => `rdc-conversation-${profil}`;
export const cleRetour = (profil: string) => `rdc-retour-${profil}`;

/** L'audience que l'investisseur vient de quitter, pour la reprendre depuis le greffier. */
export interface AudienceSuspendue {
  ticker: string;
  nomTitre: string;
  taille: number;
  question: string;
  /** Le camp retenu par l'investisseur, ou null s'il n'a pas encore voté. */
  vote: 'avocat_defense' | 'procureur' | null;
  /** Rempli seulement après le vote : la décision du tribunal reste scellée avant. */
  verdictTribunal: string | null;
  accord: boolean | null;
}

export interface Retour {
  texte: string;
  audience?: AudienceSuspendue;
}

/** Ce que le tribunal ou le duel laisse pour le greffier : un résumé à afficher au retour. */
export function laisserUnRetour(profil: string, texte: string, audience?: AudienceSuspendue): void {
  ecrire(cleRetour(profil), { texte, audience } satisfies Retour);
}

/** Un vote rendu dans un débat de la session : le greffier et le bilan de profil s'en servent. */
export interface VoteEnregistre {
  type: 'proces' | 'duel';
  ticker: string;
  nomTitre: string;
  taille: number;
  /** Procès : le camp suivi. Duel : le titre choisi. */
  vote: string;
  /** Procès : le verdict du tribunal. Duel : la décision (« XBB.TO l'emporte »). */
  verdictTribunal: string | null;
  /** Procès : votre vote rejoint-il le verdict ? */
  accord: boolean | null;
  /** Duel : l'autre titre, et celui que le tribunal a retenu. */
  adversaire?: string | null;
  gagnant?: string | null;
  /** Duel : le titre choisi fait-il baisser davantage le portefeuille que l'autre ? */
  plusRisque?: boolean | null;
}

export const cleVotes = (profil: string) => `rdc-votes-${profil}`;

export function lireVotes(profil: string): VoteEnregistre[] {
  return lire<VoteEnregistre[]>(cleVotes(profil)) ?? [];
}

/** Un même débat revoté remplace l'ancien vote ; sinon le vote s'ajoute à la fin. */
export function enregistrerVote(profil: string, v: VoteEnregistre): void {
  const meme = (x: VoteEnregistre) => x.type === v.type && x.ticker === v.ticker
    && Math.abs(x.taille - v.taille) < 1e-9 && (x.adversaire ?? null) === (v.adversaire ?? null);
  ecrire(cleVotes(profil), [...lireVotes(profil).filter((x) => !meme(x)), v]);
}
