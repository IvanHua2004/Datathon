/** Réponse de POST /api/duel : deux procès sur le même profil, puis une décision A contre B. */

export interface ChiffreDuel {
  libelle: string;
  valeur: string;
  avant: string;
  alerte: boolean;
}

export interface CoteDuel {
  ticker: string;
  nomTitre: string;
  taille: number;
  verdict: string;
  gravite: number;
  motifs: string[];
  juge: string;
  defense: string;
  procureur: string;
  avertissement: string | null;
  mode: string;
  chiffres: ChiffreDuel[];
}

export interface TourDuel {
  ordre: number;
  role: 'avocat_a' | 'avocat_b' | 'juge';
  acteur: string;
  ticker: string | null;
  texte: string;
  non_verifies: string[];
}

export interface Duel {
  debat: TourDuel[];
  avertissementDebat: string | null;
  profil: string;
  nom: string;
  cotes: [CoteDuel, CoteDuel];
  decision: { gagnant: string | null; raison: string; regle: number; titre: string; texte: string };
}
