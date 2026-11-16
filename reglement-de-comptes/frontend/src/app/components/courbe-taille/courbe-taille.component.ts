import { Component, computed, input, signal } from '@angular/core';

import { PointCourbe } from '../../models/proces.model';
import { pct } from '../../shared/format';

const LARGEUR = 780;
const HAUTEUR = 360;
const MARGE = { gauche: 74, droite: 36, haut: 32, bas: 58 };

interface PointAffiche {
  taille: number;
  pireBaisse: number;
  defavorable12Mois: number;
  partDuRisque: number;
  x: number;
  y: number;
  infobulle: string;
}

/**
 * Pire baisse observée du portefeuille selon la part placée dans le titre, face au budget.
 * Rendu haute lisibilité : zones de risque colorées, repère 0%, pilule de demande et étiquettes contrastées.
 */
@Component({
  selector: 'rdc-courbe-taille',
  templateUrl: './courbe-taille.component.html',
  styleUrl: './courbe-taille.component.scss',
})
export class CourbeTailleComponent {
  readonly pct = pct;

  readonly courbe = input.required<PointCourbe[]>();
  readonly budget = input.required<number>();
  readonly tailleDemandee = input.required<number>();
  readonly ticker = input<string>('');

  readonly survolPoint = signal<PointAffiche | null>(null);

  readonly largeur = LARGEUR;
  readonly hauteur = HAUTEUR;
  readonly marge = MARGE;

  private readonly tailleMax = computed(() => Math.max(...this.courbe().map((p) => p.taille), 0.5));

  /** Bas de l'axe : le plus bas entre la courbe et le budget, avec marge d'aération. */
  private readonly yMin = computed(() => {
    const plusBas = Math.min(this.budget(), ...this.courbe().map((p) => p.pireBaisse));
    return Math.floor((plusBas * 1.15) / 0.05) * 0.05;
  });

  private x(taille: number): number {
    const largeurUtile = LARGEUR - MARGE.gauche - MARGE.droite;
    return MARGE.gauche + (taille / this.tailleMax()) * largeurUtile;
  }

  y(valeur: number): number {
    const hauteurUtile = HAUTEUR - MARGE.haut - MARGE.bas;
    return MARGE.haut + (valeur / this.yMin()) * hauteurUtile;
  }

  readonly yZero = computed(() => this.y(0));

  readonly points = computed<PointAffiche[]>(() =>
    this.courbe().map((p) => ({
      taille: p.taille,
      pireBaisse: p.pireBaisse,
      defavorable12Mois: p.defavorable12Mois,
      partDuRisque: p.partDuRisque,
      x: this.x(p.taille),
      y: this.y(p.pireBaisse),
      infobulle:
        `Part ${pct(p.taille, 0)} · pire baisse ${pct(p.pireBaisse)} · ` +
        `cas défavorable 12 mois ${pct(p.defavorable12Mois)} · part du risque ${pct(p.partDuRisque)}`,
    })),
  );

  readonly ligne = computed(() => this.points().map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' '));

  readonly surfaceChemin = computed(() => {
    const pts = this.points();
    if (pts.length < 2) return '';
    const premier = pts[0];
    const dernier = pts[pts.length - 1];
    const lignePts = pts.map((p) => `L ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
    return `M ${premier.x.toFixed(1)} ${this.yZero().toFixed(1)} ${lignePts} L ${dernier.x.toFixed(1)} ${this.yZero().toFixed(1)} Z`;
  });

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

  badgeDemandeTransform(d: PointAffiche): string {
    const badgeW = 168;
    const badgeH = 38;
    // Décalage X avec protection contre les débordements de bord
    let bx = d.x - badgeW / 2;
    if (bx < MARGE.gauche + 5) bx = MARGE.gauche + 5;
    if (bx + badgeW > LARGEUR - MARGE.droite - 5) bx = LARGEUR - MARGE.droite - badgeW - 5;

    // Décalage Y : au-dessus si possible, sinon en dessous
    let by = d.y - badgeH - 12;
    if (by < MARGE.haut + 5) {
      by = d.y + 14;
    }
    return `translate(${bx.toFixed(1)}, ${by.toFixed(1)})`;
  }

  infobulleTransform(p: PointAffiche): string {
    const w = 140;
    const h = 34;
    let bx = p.x - w / 2;
    if (bx < MARGE.gauche + 5) bx = MARGE.gauche + 5;
    if (bx + w > LARGEUR - MARGE.droite - 5) bx = LARGEUR - MARGE.droite - w - 5;

    let by = p.y - h - 10;
    if (by < MARGE.haut + 5) by = p.y + 10;
    return `translate(${bx.toFixed(1)}, ${by.toFixed(1)})`;
  }

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
