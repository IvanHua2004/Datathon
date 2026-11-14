import { Component, computed, input } from '@angular/core';

import { PointCourbe } from '../../models/proces.model';
import { pct } from '../../shared/format';

const LARGEUR = 760;
const HAUTEUR = 340;
const MARGE = { gauche: 64, droite: 24, haut: 24, bas: 56 };

/** Pire baisse observée du portefeuille selon la part placée dans le titre, face au budget. */
@Component({
  selector: 'rdc-courbe-taille',
  template: `
    <svg [attr.viewBox]="'0 0 ' + largeur + ' ' + hauteur" role="img"
         [attr.aria-label]="description()">
      @for (t of graduationsY(); track t.valeur) {
        <line class="grille" [attr.x1]="marge.gauche" [attr.x2]="largeur - marge.droite"
              [attr.y1]="t.y" [attr.y2]="t.y"></line>
        <text class="graduation" [attr.x]="marge.gauche - 10" [attr.y]="t.y + 4" text-anchor="end">{{ t.texte }}</text>
      }
      @for (t of graduationsX(); track t.valeur) {
        <text class="graduation" [attr.x]="t.x" [attr.y]="hauteur - marge.bas + 22" text-anchor="middle">{{ t.texte }}</text>
      }
      <line class="axe" [attr.x1]="marge.gauche" [attr.x2]="largeur - marge.droite"
            [attr.y1]="hauteur - marge.bas" [attr.y2]="hauteur - marge.bas"></line>

      <line class="budget" [attr.x1]="marge.gauche" [attr.x2]="largeur - marge.droite"
            [attr.y1]="yBudget()" [attr.y2]="yBudget()"></line>
      <text class="etiquette-budget" [attr.x]="largeur - marge.droite" [attr.y]="yBudget() - 8" text-anchor="end">
        Budget de perte déclaré : {{ budgetTexte() }}
      </text>

      <polyline class="ligne" [attr.points]="ligne()"></polyline>
      @for (p of points(); track p.taille) {
        <circle class="point" [attr.cx]="p.x" [attr.cy]="p.y" r="6">
          <title>{{ p.infobulle }}</title>
        </circle>
      }
      @if (pointDemande(); as d) {
        <circle class="demande" [attr.cx]="d.x" [attr.cy]="d.y" r="13"></circle>
        <text class="etiquette-demande" [attr.x]="d.x - 16" [attr.y]="d.y + 26" text-anchor="end">Demande</text>
      }

      <text class="titre-axe" [attr.x]="(marge.gauche + largeur - marge.droite) / 2" [attr.y]="hauteur - 10" text-anchor="middle">
        Part du portefeuille placée dans le titre (%)
      </text>
      <text class="titre-axe" [attr.transform]="'translate(16 ' + (hauteur - marge.bas + marge.haut) / 2 + ') rotate(-90)'" text-anchor="middle">
        Pire baisse observée (%)
      </text>
    </svg>
  `,
  styles: `
    :host { display: block; }
    svg { width: 100%; height: auto; display: block; font-family: inherit; }
    .grille { stroke: #e8d9c4; stroke-width: 1; }
    .axe { stroke: #8a7a84; stroke-width: 1; }
    .graduation { fill: #5c4a55; font-size: 13px; }
    .titre-axe { fill: #200e0c; font-size: 13px; font-weight: 600; }
    .ligne { fill: none; stroke: #773c6f; stroke-width: 2; }
    .point { fill: #773c6f; stroke: #fff8ec; stroke-width: 2; cursor: default; }
    .demande { fill: none; stroke: #200e0c; stroke-width: 2; }
    .etiquette-demande { fill: #200e0c; font-size: 13px; font-weight: 600; }
    .budget { stroke: #200e0c; stroke-width: 1.5; stroke-dasharray: 6 4; }
    .etiquette-budget { fill: #200e0c; font-size: 13px; }
  `,
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
