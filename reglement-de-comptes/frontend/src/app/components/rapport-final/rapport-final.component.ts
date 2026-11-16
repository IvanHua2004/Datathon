import { HttpErrorResponse } from '@angular/common/http';
import { Component, ElementRef, computed, inject, input, signal, viewChild } from '@angular/core';

import { Mode, Proces, Profil } from '../../models/proces.model';
import { RapportAudienceComponent } from '../../pages/tribunal/rapport-audience.component';
import { ApiService } from '../../services/api.service';
import { pct, tonVerdict } from '../../shared/format';

type Camp = 'avocat_defense' | 'procureur';
let compteur = 0;

/**
 * Le rapport d'analyse du tribunal, en fin de parcours : une fiche « document » qui l'annonce
 * (verdict, période), puis trois gestes — le lire, le télécharger en PDF, l'imprimer.
 * Le rapport s'ouvre dans la même fenêtre papier que pendant l'audience. Si le procès
 * n'est plus en mémoire (rechargement, duel), il est recalculé sans IA : mêmes chiffres, même verdict.
 */
@Component({
  selector: 'rdc-rapport-final',
  imports: [RapportAudienceComponent],
  templateUrl: './rapport-final.component.html',
  styleUrl: './rapport-final.component.scss',
})
export class RapportFinalComponent {
  private readonly api = inject(ApiService);

  readonly profil = input<Profil | null>(null);
  readonly ticker = input.required<string>();
  readonly taille = input.required<number>();
  readonly nomTitre = input<string>('');
  /** Le procès déjà jugé dans cette session, s'il existe. */
  readonly proces = input<Proces | null>(null);
  /** Le choix de l'investisseur, repris dans le PDF. */
  readonly choix = input<'OUI' | 'NON' | null>(null);
  /** Le camp retenu au vote (procès simple), pour la mention « votre vote » du rapport. */
  readonly vote = input<Camp | null>(null);
  /** Verdict déjà connu (duel) : affiché avant même d'ouvrir le rapport. */
  readonly verdict = input<string | null>(null);
  /** « A » ou « B » dans un duel : pastille et couleur du camp. */
  readonly lettre = input<'A' | 'B' | null>(null);

  readonly pct = pct;
  /** Identifiants uniques : un duel affiche deux rapports sur la même page. */
  readonly uid = `rapport-final-${++compteur}`;
  private readonly charge = signal<Proces | null>(null);
  readonly dossier = computed(() => this.proces() ?? this.charge());
  readonly verdictAffiche = computed(() => this.dossier()?.decision.verdict ?? this.verdict());
  readonly ton = computed(() => {
    const v = this.verdictAffiche();
    return v ? tonVerdict(v) : null;
  });
  readonly interventions = computed(() =>
    (this.dossier()?.discussion ?? []).map((tour) => ({ tour, extrait: tour.texte, complet: true })));

  readonly chargement = signal(false);
  readonly chargementPdf = signal(false);
  readonly succesPdf = signal(false);
  readonly ouvert = signal(false);
  readonly erreur = signal<string | null>(null);

  private readonly fenetre = viewChild<ElementRef<HTMLDialogElement>>('fenetre');

  /** Ouvre le rapport ; le recalcule d'abord s'il n'est pas en mémoire. */
  lire(puis?: () => void): void {
    if (this.dossier()) {
      this.afficher(puis);
      return;
    }
    if (this.chargement()) return;
    this.chargement.set(true);
    this.erreur.set(null);
    this.api.ouvrirProces({ profil: this.profil()?.cle ?? '', ticker: this.ticker(), taille: this.taille(), mode: 'gabarit' })
      .subscribe({
        next: (p) => {
          this.charge.set(p);
          this.chargement.set(false);
          this.afficher(puis);
        },
        error: (e: unknown) => {
          this.chargement.set(false);
          this.erreur.set(this.message(e));
        },
      });
  }

  private afficher(puis?: () => void): void {
    const f = this.fenetre()?.nativeElement;
    if (!f) return;
    this.ouvert.set(true);
    if (!f.open) f.showModal();
    if (puis) requestAnimationFrame(() => requestAnimationFrame(puis));
  }

  telecharger(): void {
    const profil = this.profil()?.cle;
    if (!profil || this.chargementPdf()) return;
    this.chargementPdf.set(true);
    this.succesPdf.set(false);
    this.erreur.set(null);
    const mode: Mode = this.dossier()?.mode ?? 'gabarit';
    this.api.telechargerPdf(profil, this.ticker(), this.taille(), mode, undefined, this.choix() ?? undefined).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `rapport_tribunal_${profil}_${this.ticker()}.pdf`;
        a.click();
        URL.revokeObjectURL(url);
        this.chargementPdf.set(false);
        this.succesPdf.set(true);
        setTimeout(() => this.succesPdf.set(false), 3500);
      },
      error: (e: unknown) => {
        this.chargementPdf.set(false);
        this.erreur.set(this.message(e));
      },
    });
  }

  /** Imprime uniquement le papier du rapport (règles @media print globales), sections ouvertes. */
  imprimer(): void {
    this.lire(() => {
      const f = this.fenetre()?.nativeElement;
      f?.querySelectorAll('details').forEach((d) => (d.open = true));
      document.body.classList.add('impression-rapport');
      const retirer = () => {
        document.body.classList.remove('impression-rapport');
        window.removeEventListener('afterprint', retirer);
      };
      window.addEventListener('afterprint', retirer);
      window.print();
    });
  }

  fermer(): void {
    this.fenetre()?.nativeElement.close();
  }

  private message(e: unknown): string {
    return e instanceof HttpErrorResponse && typeof e.error?.detail === 'string'
      ? e.error.detail : 'Le greffe ne répond pas. Vérifiez que l’API est lancée.';
  }
}
