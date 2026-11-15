import { Component, computed, effect, inject, input } from '@angular/core';
import { RouterLink } from '@angular/router';

import { EnteteComponent } from '../../components/entete/entete.component';
import { ProcesService } from '../../services/proces.service';
import { dollars, pct } from '../../shared/format';

/** Rapport de décision, recalculable depuis les paramètres de l'URL. */
@Component({
  selector: 'rdc-rapport-comparatif',
  imports: [RouterLink, EnteteComponent],
  templateUrl: './rapport-comparatif.page.html',
  styleUrl: './rapport-comparatif.page.css',
})
export class RapportComparatifPage {
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
  readonly choixValide = computed(() => {
    const choix = (this.choix() ?? '').toUpperCase();
    return choix === 'OUI' || choix === 'NON' ? choix : null;
  });
  readonly tailleValeur = computed(() => Number(this.taille()));
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
      this.tailleValeur() <= 0.5 &&
      this.profitInitialValeur() !== null &&
      !!this.choixValide(),
  );
  readonly profitInitialIncoherent = computed(() => {
    const resultat = this.tribunal.comparaison();
    const profitInitial = this.profitInitialValeur();
    return !!resultat && (
      profitInitial === null || Math.abs(resultat.profit_initial - profitInitial) > 0.01
    );
  });
  readonly differenceProfit = computed(() => {
    const resultat = this.tribunal.comparaison();
    return resultat ? resultat.profit_final - resultat.profit_initial : 0;
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
      if (!choix || profitInitial === null) return;

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
