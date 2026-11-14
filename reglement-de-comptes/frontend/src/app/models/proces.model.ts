/** Types des réponses de l'API Python (backend/api.py). */

export type Mode = 'gabarit' | 'bedrock';

export type Verdict =
  | 'Contraire à une contrainte déclarée'
  | 'En tension avec le profil déclaré'
  | 'Indécidable : information manquante'
  | 'Compatible avec le profil déclaré';

export interface Position {
  ticker: string;
  poids: number;
}

export interface Profil {
  cle: string;
  nom: string;
  resume: string;
  objectif: string;
  preferences: string;
  capital: number;
  horizonAns: number;
  budgetPerte: number;
  plafondPosition: number;
  portefeuille: Position[];
  demandeExemple: { ticker: string; taille: number };
}

export interface Actif {
  ticker: string;
  nom: string;
  classe: string;
}

export interface Sante {
  source: { type: 's3' | 'local'; bucket: string | null; region: string };
  periode: { debut: string; fin: string };
}

export interface DemandeProces {
  profil: string;
  ticker: string;
  taille: number;
  mode: Mode;
  intention_texte?: string;
}

export interface IntentionResultat {
  ticker: string;
  taille: number;
  nomTitre: string;
  classe: string;
  explication: string;
}

export interface AnalyseComparative {
  choix: boolean;
  titre_decision: string;
  statut_conformite: string;
  impact_capital: string;
  delta_perte_dollars: number;
  perte_max_dollars: number;
  budget_depasse: boolean;
  montant_depassement: number;
  volatilite_finale: number;
  delta_volatilite: number;
  temps_recuperation: string;
  commentaire_conseil: string;
  recommandations: string[];
}

export interface ScenarioAlternatif {
  nom: string;
  type: string;
  description: string;
  allocation: Record<string, number>;
  pire_baisse: number;
  perte_dollars: number;
  volatilite: number;
  verdict: Verdict;
  pourquoi: string;
}

export interface Motif {
  temoin: string;
  texte: string;
}

export interface Plaidoirie {
  role: string;
  texte: string;
  temoins_convoques: string[];
  non_verifies: string[];
}

export interface HypotheseSalle {
  hypothese: string;
  verdict: Verdict;
  change: boolean;
}

export interface PointCourbe {
  taille: number;
  pireBaisse: number;
  defavorable12Mois: number;
  partDuRisque: number;
}

export interface Piece {
  numero: string;
  temoin: string;
  description: string;
  outil: string;
  appelePar: string;
  horodatage: string;
  faits: { libelle: string; valeur: string }[];
  source: string;
  periode: string;
  limites: string;
}

export interface Proces {
  demande: {
    profil: string;
    nom: string;
    ticker: string;
    nomTitre: string;
    taille: number;
    capital: number;
  };
  periode: { debut: string; fin: string };
  mode: Mode;
  avertissement: string | null;
  decision: {
    verdict: Verdict;
    contraintes: Motif[];
    tensions: Motif[];
    manquants: Motif[];
  };
  plaidoiries: Plaidoirie[];
  motivation: Plaidoirie;
  salle: HypotheseSalle[];
  courbe: PointCourbe[];
  budgetPerte: number;
  pieces: Piece[];
  rapport_explicabilite?: string;
}
