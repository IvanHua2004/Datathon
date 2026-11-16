import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';

import { EnteteComponent } from '../../components/entete/entete.component';
import { RapportFinalComponent } from '../../components/rapport-final/rapport-final.component';
import { CoteDuel, Duel } from '../../models/duel.model';
import { AnalyseComparative } from '../../models/proces.model';
import { ApiService } from '../../services/api.service';
import { ProcesService } from '../../services/proces.service';
import { SonAudienceService } from '../../services/son-audience.service';
import { cleDuel, relireDuel } from '../../shared/duel-memoire';
import { dollars, pct, tonVerdict } from '../../shared/format';

/** Lit « NVDA:0.1 » dans l'URL. */
function lireCote(texte: string): { ticker: string; taille: number } | null {
  const [ticker, taille] = texte.split(':');
  const t = Number(taille);
  return ticker && t > 0 && t <= 0.5 ? { ticker, taille: t } : null;
}

type Cote = 'a' | 'b';
type Meilleur = Cote | 'egal' | null;

/** Une ligne du face-à-face : la meilleure des deux valeurs est marquée. */
interface LigneDuel {
  libelle: string;
  aide: string;
  a: string;
  b: string;
  meilleur: Meilleur;
  alerteA?: boolean;
  alerteB?: boolean;
}

/** Plus grand gagne (profit) ou plus petit gagne (perte, volatilité). */
function departager(a: number, b: number, plusGrandGagne: boolean): Meilleur {
  if (Math.abs(a - b) < 1e-9) return 'egal';
  return (a > b) === plusGrandGagne ? 'a' : 'b';
}

/**
 * Le tableau de bord comparatif d'un duel : le même rapport que pour un titre,
 * mais les deux dossiers côte à côte — décision, profits simulés, pertes face au budget,
 * risque, chiffres du dossier, motifs et recommandations.
 */
@Component({
  selector: 'rdc-rapport-duel',
  imports: [RouterLink, EnteteComponent, RapportFinalComponent],
  templateUrl: './rapport-duel.page.html',
  styleUrl: './rapport-duel.page.scss',
})
export class RapportDuelPage {
  private readonly api = inject(ApiService);
  private readonly tribunal = inject(ProcesService);
  readonly sonAudience = inject(SonAudienceService);

  /** /rapport-duel?profil=robert&a=NVDA:0.1&b=XBB.TO:0.1&vote=NVDA */
  readonly profilCle = input('', { alias: 'profil' });
  readonly a = input('');
  readonly b = input('');
  readonly vote = input('');

  readonly pct = pct;
  readonly dollars = dollars;
  readonly tonVerdict = tonVerdict;
  private readonly formatCAD = new Intl.NumberFormat('fr-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 0 });
  readonly cad = (x: number) => this.formatCAD.format(x);

  readonly comparaisons = signal<{ a: AnalyseComparative; b: AnalyseComparative } | null>(null);
  readonly chargement = signal(false);
  readonly erreur = signal<string | null>(null);

  readonly profil = computed(() => this.tribunal.profils().find((p) => p.cle === this.profilCle()) ?? null);
  readonly coteA = computed(() => lireCote(this.a()));
  readonly coteB = computed(() => lireCote(this.b()));
  readonly demandeValide = computed(() => !!this.profilCle() && !!this.coteA() && !!this.coteB());
  /** Le duel jugé juste avant (décision, verdicts, chiffres du dossier), s'il est encore en mémoire. */
  readonly duel = computed<Duel | null>(() => relireDuel(cleDuel(this.profilCle(), this.a(), this.b())));
  readonly dossiers = computed<[CoteDuel, CoteDuel] | null>(() => this.duel()?.cotes ?? null);
  readonly nomA = computed(() => this.dossiers()?.[0].nomTitre ?? this.nomActif(this.coteA()?.ticker));
  readonly nomB = computed(() => this.dossiers()?.[1].nomTitre ?? this.nomActif(this.coteB()?.ticker));

  readonly gagnant = computed<Cote | null>(() => {
    const g = this.duel()?.decision.gagnant;
    if (!g) return null;
    return g === this.coteA()?.ticker ? 'a' : g === this.coteB()?.ticker ? 'b' : null;
  });
  readonly voteCote = computed<Cote | null>(() =>
    this.vote() === this.coteA()?.ticker ? 'a' : this.vote() === this.coteB()?.ticker ? 'b' : null);

  /** Le bandeau du haut : votre vote face à la décision du tribunal. */
  readonly bilan = computed(() => {
    const d = this.duel();
    const vote = this.voteCote();
    const tickerVote = vote === 'a' ? this.coteA()?.ticker : vote === 'b' ? this.coteB()?.ticker : null;
    if (!d) {
      return {
        ton: 'incertain',
        titre: 'Les deux dossiers côte à côte',
        detail: 'La décision du duel n’est plus en mémoire : rejouez le duel pour la retrouver. Les chiffres ci-dessous sont recalculés.',
      };
    }
    if (!vote) return { ton: 'incertain', titre: d.decision.titre, detail: `${d.decision.raison}.` };
    if (!this.gagnant()) {
      return { ton: 'incertain', titre: `Vous avez voté pour ${tickerVote} ; le tribunal ne départage pas`, detail: `${d.decision.raison}.` };
    }
    const accord = vote === this.gagnant();
    return {
      ton: accord ? 'accord' : 'ecart',
      titre: accord ? `Vous avez voté pour ${tickerVote} : le tribunal vous rejoint`
        : `Vous avez voté pour ${tickerVote} : le tribunal tranche autrement`,
      detail: `${d.decision.titre}. Motif : ${d.decision.raison}.`,
    };
  });

  readonly budgetDollars = computed(() => {
    const p = this.profil();
    return p && p.capital > 0 ? Math.abs(p.budgetPerte) * p.capital : null;
  });

  /** Le face-à-face chiffré, recalculé sur la même période historique pour les deux titres. */
  readonly lignes = computed<LigneDuel[]>(() => {
    const c = this.comparaisons();
    if (!c) return [];
    const budget = this.budgetDollars();
    const horsBudget = (x: AnalyseComparative) => budget !== null ? Math.abs(x.perte_max_dollars) - budget > 0.01 : x.budget_depasse;
    return [
      {
        libelle: 'Profit simulé', aide: 'Sur toute la période historique, avec la position ajoutée',
        a: this.cad(c.a.profit_final), b: this.cad(c.b.profit_final),
        meilleur: departager(c.a.profit_final, c.b.profit_final, true),
      },
      {
        libelle: 'Écart vs portefeuille initial', aide: `Le portefeuille sans changement fait ${this.cad(c.a.profit_initial)}`,
        a: this.signe(c.a.profit_final - c.a.profit_initial), b: this.signe(c.b.profit_final - c.b.profit_initial),
        meilleur: departager(c.a.profit_final, c.b.profit_final, true),
      },
      {
        libelle: 'Pire perte simulée', aide: budget !== null ? `Budget de perte déclaré : ${this.cad(budget)}` : 'Le plus gros recul du portefeuille',
        a: this.cad(c.a.perte_max_dollars), b: this.cad(c.b.perte_max_dollars),
        meilleur: departager(Math.abs(c.a.perte_max_dollars), Math.abs(c.b.perte_max_dollars), false),
        alerteA: horsBudget(c.a), alerteB: horsBudget(c.b),
      },
      {
        libelle: 'Budget de perte', aide: 'La pire perte reste-t-elle dans la limite déclarée ?',
        a: horsBudget(c.a) ? 'Dépassé' : 'Respecté', b: horsBudget(c.b) ? 'Dépassé' : 'Respecté',
        meilleur: horsBudget(c.a) === horsBudget(c.b) ? 'egal' : horsBudget(c.a) ? 'b' : 'a',
        alerteA: horsBudget(c.a), alerteB: horsBudget(c.b),
      },
      {
        libelle: 'Volatilité annualisée', aide: 'À quel point le portefeuille bouge d’une année à l’autre',
        a: pct(c.a.volatilite_finale), b: pct(c.b.volatilite_finale),
        meilleur: departager(c.a.volatilite_finale, c.b.volatilite_finale, false),
      },
      {
        libelle: 'Variation de volatilité', aide: 'Par rapport au portefeuille de départ',
        a: this.signePct(c.a.delta_volatilite), b: this.signePct(c.b.delta_volatilite),
        meilleur: departager(c.a.delta_volatilite, c.b.delta_volatilite, false),
      },
      {
        libelle: 'Temps sous le sommet', aide: 'Durée historique avant de retrouver le plus haut',
        a: c.a.temps_recuperation, b: c.b.temps_recuperation, meilleur: null,
      },
    ];
  });

  /** Score du face-à-face : combien de lignes chaque titre remporte. */
  readonly score = computed(() => {
    const l = this.lignes();
    return {
      a: l.filter((x) => x.meilleur === 'a').length,
      b: l.filter((x) => x.meilleur === 'b').length,
      total: l.filter((x) => x.meilleur !== null).length,
    };
  });

  /** Barres des profits : portefeuille initial, avec A, avec B (même échelle). */
  readonly barresProfit = computed(() => {
    const c = this.comparaisons();
    if (!c) return [];
    const valeurs = [
      { cle: 'initial', libelle: 'Portefeuille initial', valeur: c.a.profit_initial },
      { cle: 'a', libelle: `Avec ${this.coteA()?.ticker}`, valeur: c.a.profit_final },
      { cle: 'b', libelle: `Avec ${this.coteB()?.ticker}`, valeur: c.b.profit_final },
    ];
    const max = Math.max(...valeurs.map((v) => Math.abs(v.valeur)), 1);
    return valeurs.map((v) => ({ ...v, largeur: Math.max(2, (Math.abs(v.valeur) / max) * 100), negatif: v.valeur < 0 }));
  });

  /** Barres de la pire perte face au budget déclaré (la ligne verticale). */
  readonly barresPerte = computed(() => {
    const c = this.comparaisons();
    if (!c) return null;
    const budget = this.budgetDollars();
    const valeurs = [
      { cle: 'a', libelle: this.coteA()?.ticker ?? 'A', valeur: Math.abs(c.a.perte_max_dollars) },
      { cle: 'b', libelle: this.coteB()?.ticker ?? 'B', valeur: Math.abs(c.b.perte_max_dollars) },
    ];
    const max = Math.max(...valeurs.map((v) => v.valeur), budget ?? 0, 1) * 1.08;
    return {
      budget: budget !== null ? { valeur: budget, position: (budget / max) * 100 } : null,
      barres: valeurs.map((v) => ({ ...v, largeur: (v.valeur / max) * 100, depasse: budget !== null && v.valeur > budget + 0.01 })),
    };
  });

  /** Les chiffres du dossier scellé : avant, avec A, avec B. */
  readonly chiffresDossier = computed(() => {
    const d = this.dossiers();
    if (!d) return [];
    return d[0].chiffres.map((x) => ({
      libelle: x.libelle,
      avant: x.avant,
      a: x.valeur,
      alerteA: x.alerte,
      b: d[1].chiffres.find((y) => y.libelle === x.libelle)?.valeur ?? '—',
      alerteB: d[1].chiffres.find((y) => y.libelle === x.libelle)?.alerte ?? false,
    }));
  });

  constructor() {
    this.tribunal.chargerReferentiels();
    let dernier = '';
    effect(() => {
      const a = this.coteA();
      const b = this.coteB();
      if (!this.demandeValide() || !a || !b) return;
      const cle = cleDuel(this.profilCle(), this.a(), this.b());
      if (cle === dernier) return;
      dernier = cle;
      this.chargement.set(true);
      this.erreur.set(null);
      forkJoin({
        a: this.api.comparerDecision(this.profilCle(), a.ticker, a.taille, 'OUI', null),
        b: this.api.comparerDecision(this.profilCle(), b.ticker, b.taille, 'OUI', null),
      }).subscribe({
        next: (c) => {
          this.comparaisons.set(c);
          this.chargement.set(false);
        },
        error: (e: unknown) => {
          this.chargement.set(false);
          this.erreur.set(e instanceof HttpErrorResponse && typeof e.error?.detail === 'string'
            ? e.error.detail : 'Le greffe ne répond pas. Vérifiez que l’API est lancée.');
        },
      });
    });
  }

  private nomActif(ticker: string | undefined): string {
    return this.tribunal.actifs().find((x) => x.ticker === ticker)?.nom ?? ticker ?? '';
  }

  private signe(x: number): string {
    return (x > 0 ? '+' : '') + this.cad(x);
  }

  private signePct(x: number): string {
    return (x > 0 ? '+' : '') + pct(x);
  }
}
