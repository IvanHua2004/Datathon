import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { EnteteComponent } from '../../components/entete/entete.component';
import { Duel } from '../../models/duel.model';
import { ApiService } from '../../services/api.service';
import { pct, tonVerdict } from '../../shared/format';

/** Lit « NVDA:0.1 » dans l'URL. */
function lireCote(texte: string): { ticker: string; taille: number } | null {
  const [ticker, taille] = texte.split(':');
  const t = Number(taille);
  return ticker && t > 0 && t <= 0.5 ? { ticker, taille: t } : null;
}

/** Le duel : deux titres jugés sur le même profil, puis une décision A contre B. */
@Component({
  selector: 'rdc-duel',
  imports: [RouterLink, EnteteComponent],
  templateUrl: './duel.page.html',
  styleUrl: './duel.page.css',
})
export class DuelPage {
  private readonly api = inject(ApiService);

  /** /duel?profil=robert&a=NVDA:0.1&b=XBB.TO:0.1 */
  readonly profil = input<string>('');
  readonly a = input<string>('');
  readonly b = input<string>('');

  readonly duel = signal<Duel | null>(null);
  readonly erreur = signal<string | null>(null);
  readonly enCours = signal(false);

  readonly pct = pct;
  readonly tonVerdict = tonVerdict;

  readonly cotes = computed(() => [lireCote(this.a()), lireCote(this.b())]);
  readonly avertissement = computed(() => this.duel()?.cotes.find((c) => c.avertissement)?.avertissement ?? null);

  private lance = '';

  constructor() {
    effect(() => {
      const [a, b] = this.cotes();
      const cle = `${this.profil()}|${this.a()}|${this.b()}`;
      if (!this.profil() || !a || !b || cle === this.lance) return;
      this.lance = cle;
      this.juger(a, b);
    });
  }

  private juger(a: { ticker: string; taille: number }, b: { ticker: string; taille: number }): void {
    this.enCours.set(true);
    this.erreur.set(null);
    this.duel.set(null);
    this.api.duel(this.profil(), a, b).subscribe({
      next: (d) => {
        this.duel.set(d);
        this.enCours.set(false);
      },
      error: (e: unknown) => {
        this.enCours.set(false);
        this.erreur.set(
          e instanceof HttpErrorResponse && typeof e.error?.detail === 'string'
            ? e.error.detail
            : "Le tribunal ne répond pas. Vérifiez que l'API est lancée.",
        );
      },
    });
  }

  gagnant(ticker: string): boolean {
    return this.duel()?.decision.gagnant === ticker;
  }
}
