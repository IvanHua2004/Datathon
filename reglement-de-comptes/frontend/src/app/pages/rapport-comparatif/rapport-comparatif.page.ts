import { Component, computed, effect, inject, input } from '@angular/core';
import { RouterLink } from '@angular/router';

import { EnteteComponent } from '../../components/entete/entete.component';
import { ProfilReveleComponent } from '../../components/profil-revele/profil-revele.component';
import { RapportFinalComponent } from '../../components/rapport-final/rapport-final.component';
import { lireVotes } from '../../shared/memoire';
import { ProcesService } from '../../services/proces.service';
import { dollars, pct, tonVerdict } from '../../shared/format';

/** Rapport de décision, recalculable depuis les paramètres de l'URL. */
@Component({
  selector: 'rdc-rapport-comparatif',
  imports: [RouterLink, EnteteComponent, RapportFinalComponent, ProfilReveleComponent],
  templateUrl: './rapport-comparatif.page.html',
  styleUrl: './rapport-comparatif.page.scss',
})
export class RapportComparatifPage {
  /** Tous les votes de la session pour ce profil : le bilan « d'après vos choix » les relit. */
  readonly votes = computed(() => lireVotes(this.profilCle()));
  readonly tribunal = inject(ProcesService);

  readonly profilCle = input('', { alias: 'profil' });
  readonly ticker = input('');
  readonly taille = input('');
  readonly choix = input('');
  readonly profitInitial = input('');

  readonly pct = pct;
  readonly dollars = dollars;
  private readonly formatCAD = new Intl.NumberFormat('fr-CA', {
    style: 'currency',
    currency: 'CAD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  readonly dollarsPrecises = (valeur: number) => this.formatCAD.format(valeur);

  readonly profil = computed(
    () => this.tribunal.profils().find((profil) => profil.cle === this.profilCle()) ?? null,
  );
  readonly actif = computed(
    () => this.tribunal.actifs().find((actif) => actif.ticker === this.ticker()) ?? null,
  );
  readonly tailleValeur = computed(() => Number(this.taille()));
  readonly procesDuDossier = computed(() =>
    this.tribunal.correspond(this.profilCle(), this.ticker(), this.tailleValeur())
      ? this.tribunal.resultat() : null,
  );
  readonly choixValide = computed(() => {
    const choix = (this.choix() ?? '').toUpperCase();
    if (choix === 'OUI' || choix === 'NON') return choix;
    return this.procesDuDossier() ? this.tribunal.choixInvestisseur() : null;
  });
  readonly profitInitialValeur = computed(() => {
    const valeur = (this.profitInitial() ?? '').trim();
    if (!valeur) return null;
    const profit = Number(valeur);
    return Number.isFinite(profit) ? profit : null;
  });
  readonly parametresRetourVote = computed(() => ({
    profil: this.profilCle(),
    ticker: this.ticker(),
    taille: this.tailleValeur(),
    retour: 'vote',
  }));
  readonly demandeValide = computed(
    () =>
      !!this.profilCle() &&
      !!this.ticker() &&
      this.tailleValeur() > 0 &&
      this.tailleValeur() <= 0.5,
  );
  readonly profitInitialIncoherent = computed(() => {
    const resultat = this.tribunal.comparaison();
    const profitInitial = this.profitInitialValeur();
    return !!resultat && profitInitial !== null && Math.abs(resultat.profit_initial - profitInitial) > 0.01;
  });
  readonly differenceProfit = computed(() => {
    const resultat = this.tribunal.comparaison();
    return resultat ? resultat.profit_final - resultat.profit_initial : 0;
  });
  readonly budgetDeclare = computed(() => {
    const profil = this.profil();
    return profil && profil.capital > 0 ? Math.abs(profil.budgetPerte) * profil.capital : null;
  });
  readonly ecartBudget = computed(() => {
    const budget = this.budgetDeclare();
    const comparaison = this.tribunal.comparaison();
    return budget !== null && comparaison ? Math.abs(comparaison.perte_max_dollars) - budget : null;
  });
  readonly perteHorsBudget = computed(() => {
    const ecart = this.ecartBudget();
    return ecart !== null ? ecart > 0.01 : !!this.tribunal.comparaison()?.budget_depasse;
  });
  readonly bilanProfil = computed(() => {
    const comparaison = this.tribunal.comparaison();
    if (!comparaison) return null;

    const budget = this.budgetDeclare();
    const verdict = this.procesDuDossier()?.decision.verdict;
    const ton = verdict ? tonVerdict(verdict) : null;

    if (this.perteHorsBudget()) {
      const ecart = this.ecartBudget() ?? comparaison.montant_depassement;
      return {
        ton: 'ecart',
        titre: 'Votre choix dépasse le budget de perte déclaré',
        detail: `La pire perte simulée excède la limite du persona de ${this.dollarsPrecises(ecart)}.`,
      };
    }
    if (!comparaison.choix) {
      return {
        ton: budget !== null ? 'accord' : 'incertain',
        titre: 'Votre choix conserve le portefeuille initial',
        detail: budget !== null
          ? 'Vous renoncez à la position proposée. Le risque reste celui du portefeuille de départ, dans le budget déclaré sur la période simulée.'
          : 'Vous renoncez à la position proposée. Le risque reste celui du portefeuille de départ.',
      };
    }
    if (ton === 'contraire' || ton === 'tension' || comparaison.statut_conformite.startsWith('Divergence')) {
      return {
        ton: 'ecart',
        titre: ton === 'tension' ? 'Votre choix est en tension avec le profil déclaré' : 'Votre choix s’écarte du profil déclaré',
        detail: verdict ? `Vous maintenez l’investissement. Avis du juge : « ${verdict} ».`
          : 'Vous maintenez l’investissement malgré les réserves relevées dans le dossier.',
      };
    }
    if (ton === 'compatible') {
      return {
        ton: 'accord',
        titre: 'Votre choix est cohérent avec le profil déclaré',
        detail: 'Vous retenez un investissement jugé compatible avec les contraintes déclarées.',
      };
    }
    return {
      ton: 'incertain',
      titre: 'Cohérence avec le profil à confirmer',
      detail: 'La simulation mesure le risque pris et permet de le comparer au budget déclaré.',
    };
  });
  readonly evolutionProfit = computed(() => {
    const resultat = this.tribunal.comparaison();
    if (!resultat || resultat.profit_initial === 0) return null;
    return this.differenceProfit() / resultat.profit_initial;
  });

  private dernierDossier = '';

  constructor() {
    this.tribunal.chargerReferentiels();
    effect(() => {
      if (!this.demandeValide()) return;
      const choix = this.choixValide();
      const profitInitial = this.profitInitialValeur();
      if (!choix) return;

      const dossier = `${this.profilCle()}|${this.ticker()}|${this.tailleValeur()}|${choix}|${profitInitial}`;
      if (dossier === this.dernierDossier) return;
      this.dernierDossier = dossier;
      this.tribunal.choisirArbitrage(
        choix,
        this.profilCle(),
        this.ticker(),
        this.tailleValeur(),
        profitInitial,
      );
    });
  }
}
