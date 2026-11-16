import { Component, computed, input } from '@angular/core';

import { PointCourbe } from '../../models/proces.model';
import { pct } from '../../shared/format';

const LARGEUR = 760;
const HAUTEUR = 340;
const MARGE = { gauche: 64, droite: 24, haut: 24, bas: 56 };

/** Pire baisse observée du portefeuille selon la part placée dans le titre, face au budget. */
@Component({
  selector: 'rdc-courbe-taille',
  templateUrl: './courbe-taille.component.html',
  styleUrl: './courbe-taille.component.scss',
})
export class CourbeTailleComponent {
  readonly courbe = input.required<PointCourbe[]>();
  readonly budget = input.required<number>();
  readonly tailleDemandee = input.required<number>();
  readonly ticker = input<string>('');

  readonly largeur = LARGEUR;
  readonly hauteur = HAUTEUR;
  readonly marge = MARGE;

  private readonly tailleMax = computed(() => Math.max(...this.courbe().map((p) => p.taille), 0.5));

  /** Bas de l'axe : le plus bas entre la courbe et le budget, arrondi à 10 points. */
  private readonly yMin = computed(() => {
    const plusBas = Math.min(this.budget(), ...this.courbe().map((p) => p.pireBaisse));
    return Math.floor((plusBas * 1.08) / 0.1) * 0.1;
  });

  private x(taille: number): number {
    const largeurUtile = LARGEUR - MARGE.gauche - MARGE.droite;
    return MARGE.gauche + (taille / this.tailleMax()) * largeurUtile;
  }

  private y(valeur: number): number {
    const hauteurUtile = HAUTEUR - MARGE.haut - MARGE.bas;
    return MARGE.haut + (valeur / this.yMin()) * hauteurUtile;
  }

  readonly points = computed(() =>
    this.courbe().map((p) => ({
      taille: p.taille,
      x: this.x(p.taille),
      y: this.y(p.pireBaisse),
      infobulle:
        `Part ${pct(p.taille, 0)} · pire baisse ${pct(p.pireBaisse)} · ` +
        `cas défavorable 12 mois ${pct(p.defavorable12Mois)} · part du risque ${pct(p.partDuRisque)}`,
    })),
  );

  readonly ligne = computed(() => this.points().map((p) => `${p.x},${p.y}`).join(' '));

  readonly pointDemande = computed(() =>
    this.points().find((p) => Math.abs(p.taille - this.tailleDemandee()) < 1e-9) ?? null,
  );

  readonly yBudget = computed(() => this.y(this.budget()));
  readonly budgetTexte = computed(() => pct(this.budget(), 0));

  readonly graduationsY = computed(() => {
    const pas = this.yMin() > -0.25 ? 0.05 : 0.1;
    const resultat = [];
    for (let v = 0; v >= this.yMin() - 1e-9; v -= pas) {
      resultat.push({ valeur: v, y: this.y(v), texte: pct(v, 0) });
    }
    return resultat;
  });

  readonly graduationsX = computed(() => {
    const resultat = [];
    for (let v = 0; v <= this.tailleMax() + 1e-9; v += 0.1) {
      resultat.push({ valeur: v, x: this.x(v), texte: `${Math.round(v * 100)}` });
    }
    return resultat;
  });

  readonly description = computed(() => {
    const d = this.pointDemande();
    const demande = this.courbe().find((p) => Math.abs(p.taille - this.tailleDemandee()) < 1e-9);
    return (
      `Pire baisse observée du portefeuille selon la part placée dans ${this.ticker()}. ` +
      (demande && d ? `À la taille demandée (${pct(demande.taille, 0)}) : ${pct(demande.pireBaisse)}. ` : '') +
      `Budget de perte déclaré : ${this.budgetTexte()}.`
    );
  });
}
