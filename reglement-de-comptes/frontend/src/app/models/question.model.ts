/** Réponse du greffier à une question (POST /api/questions/analyser). */

export type StatutQuestion =
  | 'recevable' | 'choix' | 'incomplet' | 'refus'
  | 'fiche' | 'comparaison' | 'catalogue' | 'selection' | 'profil' | 'definition' | 'social';

/** Un dossier que le greffier propose quand la question est vague ou porte sur plusieurs titres. */
export interface ChoixDossier {
  ticker: string;
  nomTitre: string;
  taille: number;
  question: string;
  raison: string;
}

export interface AnalyseQuestion {
  statut: StatutQuestion;
  motif: string;
  message: string;
  ticker: string | null;
  nomTitre: string | null;
  taille: number | null;
  question: string | null;
  reformulations: string[];
  choix: ChoixDossier[];
  theme: string | null;
  /** Qui répond : le greffier, ou l'archiviste pour les questions de chiffres. */
  agent: 'greffier' | 'archiviste';
  fiches: FicheTitre[];
  /** Catalogue des actifs, ou titres à choisir pour une comparaison. */
  groupes: GroupeTitres[];
  /** « deux » : choisir deux titres; « un_par_groupe » : un titre dans chaque domaine. */
  selection: 'deux' | 'un_par_groupe' | null;
  /** Dossier de l'investisseur (statut « profil »). */
  profil: DossierInvestisseur | null;
  /** Terme du glossaire (statut « definition »). */
  definition: { terme: string; texte: string; exemple: string | null } | null;
}

export interface DossierInvestisseur {
  cle: string;
  nom: string;
  resume: string;
  objectif: string;
  preferences: string;
  capital: number;
  horizonAns: number;
  budgetPerte: number;
  plafondPosition: number;
  plafondSecteur: number;
  classesExclues: string[];
  filtreEsg: boolean;
  secteursAJustifier: string[];
  portefeuille: { ticker: string; nomTitre: string; classe: string; poids: number }[];
}

export interface TitreCatalogue {
  ticker: string;
  nomTitre: string;
  secteur: string;
  dansPortefeuille: boolean;
  exclu: boolean;
}

export interface GroupeTitres {
  nom: string;
  titres: TitreCatalogue[];
}

/** Fiche de l'archiviste : les chiffres d'un titre, tirés du jeu de données seulement. */
export interface FicheTitre {
  ticker: string;
  nomTitre: string;
  classe: string;
  secteur: string;
  marche: string;
  devise: string;
  periode: { debut: string; fin: string };
  faits: { libelle: string; valeur: string; aide: string }[];
  source: string;
  limites: string;
}

export interface DemandeAnalyse {
  texte: string;
  profil: string;
  ticker?: string | null;
  taille?: number | null;
  /** Deux titres (ou « MOY:<domaine> ») choisis à l'écran pour une comparaison. */
  comparer?: [string, string];
  /** Boutons de l'écran : voir tous les titres, ou en choisir deux à comparer. */
  action?: 'catalogue' | 'choisir_deux';
  /** Questions précédentes, de la plus ancienne à la plus récente (la plus récente a priorité). */
  historique?: string[];
}
