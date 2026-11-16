import { HttpErrorResponse } from '@angular/common/http';
import { NgTemplateOutlet } from '@angular/common';
import { Component, ElementRef, afterRenderEffect, computed, effect, inject, input, signal, viewChild } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { EnteteComponent } from '../../components/entete/entete.component';
import { Duel } from '../../models/duel.model';
import { ApiService } from '../../services/api.service';
import { ProcesService } from '../../services/proces.service';
import { SonAudienceService } from '../../services/son-audience.service';
import { pct, tonVerdict } from '../../shared/format';
import { laisserUnRetour } from '../../shared/memoire';
import { AudienceSceneComponent, ConfigDuel } from '../tribunal/audience-scene.component';

type Camp = 'avocat_defense' | 'procureur';

/** Lit « NVDA:0.1 » dans l'URL. */
function lireCote(texte: string): { ticker: string; taille: number } | null {
  const [ticker, taille] = texte.split(':');
  const t = Number(taille);
  return ticker && t > 0 && t <= 0.5 ? { ticker, taille: t } : null;
}

/** Les chiffres qui départagent le mieux deux dossiers, dans le rail du vote. */
const TUILES = ['Pire baisse du portefeuille', 'Volatilité annuelle', 'Résultat en 2022', 'Part du risque due au titre'];

/**
 * Le duel : la même audience animée qu'un procès simple, mais la question posée au tribunal
 * est « A ou B ? ». Me Vigor défend A, Me Austère défend B ; l'investisseur vote, puis la
 * règle fixe du duel tranche et le détail des deux dossiers s'affiche.
 */
@Component({
  selector: 'rdc-duel',
  host: { class: 'tribunal-scene' },
  imports: [RouterLink, NgTemplateOutlet, EnteteComponent, AudienceSceneComponent],
  templateUrl: './duel.page.html',
  styleUrl: './duel.page.css',
})
export class DuelPage {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly tribunal = inject(ProcesService);
  readonly sonAudience = inject(SonAudienceService);

  /** /duel?profil=robert&a=NVDA:0.1&b=XBB.TO:0.1 */
  readonly profil = input<string>('');
  readonly a = input<string>('');
  readonly b = input<string>('');

  readonly duel = signal<Duel | null>(null);
  readonly erreur = signal<string | null>(null);
  readonly enCours = signal(false);
  /** Le détail des deux dossiers ne s'affiche qu'après le vote, pour ne pas l'influencer. */
  readonly decisionVisible = signal(false);
  readonly vote = signal<Camp | null>(null);
  /** Chaque demande de « voir la décision » fait défiler jusqu'à elle. */
  private readonly defilement = signal(0);

  readonly pct = pct;
  readonly tonVerdict = tonVerdict;

  readonly scene = viewChild(AudienceSceneComponent);
  private readonly blocDecision = viewChild<ElementRef<HTMLElement>>('blocDecision');

  readonly persona = computed(() => this.tribunal.profils().find((p) => p.cle === this.profil()) ?? null);
  readonly cotes = computed(() => [lireCote(this.a()), lireCote(this.b())]);
  readonly avertissement = computed(() => this.duel()?.cotes.find((c) => c.avertissement)?.avertissement ?? null);
  readonly question = computed(() => {
    const d = this.duel();
    if (d) return d.question;
    const [a, b] = this.cotes();
    return a && b ? `${a.ticker} ou ${b.ticker}, lequel convient le mieux à ${pct(a.taille, 0)} du portefeuille ?` : '';
  });
  readonly messageAttente = computed(() => {
    const [a, b] = this.cotes();
    const titres = a && b ? `${a.ticker} et ${b.ticker}` : 'les deux titres';
    return `Les parties préparent deux dossiers en même temps : ${titres}. Avec Bedrock, comptez environ 30 secondes.`;
  });

  readonly config = computed<ConfigDuel | null>(() => {
    const d = this.duel();
    if (!d) return null;
    const [a, b] = d.cotes;
    const ligne = (libelle: string) => {
      const x = a.chiffres.find((c) => c.libelle === libelle);
      const y = b.chiffres.find((c) => c.libelle === libelle);
      return x && y ? [{ libelle: libelle.replace(' du portefeuille', '').replace(' due au titre', ''),
        a: x.valeur, b: y.valeur, alerteA: x.alerte, alerteB: y.alerte }] : [];
    };
    return {
      camps: {
        avocat_defense: { ticker: a.ticker, nomTitre: a.nomTitre },
        procureur: { ticker: b.ticker, nomTitre: b.nomTitre },
      },
      annonce: `${d.decision.titre} : ${d.decision.raison}. Cette simulation n’est pas un conseil financier.`,
      tuiles: TUILES.flatMap(ligne),
    };
  });

  private lance = '';

  constructor() {
    this.tribunal.chargerReferentiels();
    effect(() => {
      const [a, b] = this.cotes();
      const cle = `${this.profil()}|${this.a()}|${this.b()}`;
      if (!this.profil() || !a || !b || cle === this.lance) return;
      this.lance = cle;
      this.juger(a, b);
    });
    // Après le vote et l'annonce du juge : le détail du duel apparaît sous la salle.
    afterRenderEffect(() => {
      if (!this.defilement() || !this.decisionVisible()) return;
      this.blocDecision()?.nativeElement.scrollIntoView({
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
        block: 'start',
      });
    });
  }

  private juger(a: { ticker: string; taille: number }, b: { ticker: string; taille: number }): void {
    this.enCours.set(true);
    this.erreur.set(null);
    this.duel.set(null);
    this.vote.set(null);
    this.decisionVisible.set(false);
    this.defilement.set(0);
    this.api.duel(this.profil(), a, b).subscribe({
      next: (d) => {
        this.duel.set(d);
        this.laisserRetour(d);
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

  /** Le greffier résume le duel au retour ; la décision n'y figure qu'après le vote. */
  private laisserRetour(d: Duel, camp: Camp | null = null): void {
    const [a, b] = d.cotes;
    const choisi = camp === 'avocat_defense' ? a.ticker : camp === 'procureur' ? b.ticker : null;
    laisserUnRetour(d.profil, `Retour du duel ${a.ticker} contre ${b.ticker}`
      + (choisi ? ` : vous avez voté pour ${choisi}. ${d.decision.titre}.` : ', avant votre vote.'));
  }

  voter(camp: Camp): void {
    this.vote.set(camp);
    this.decisionVisible.set(true);
    const d = this.duel();
    if (d) this.laisserRetour(d, camp);
  }

  montrerDecision(): void {
    this.decisionVisible.set(true);
    this.defilement.update((n) => n + 1);
  }

  versGreffier(): void {
    this.router.navigate(['/question'], { queryParams: { profil: this.profil() } });
  }

  gagnant(ticker: string): boolean {
    return this.duel()?.decision.gagnant === ticker;
  }
}
