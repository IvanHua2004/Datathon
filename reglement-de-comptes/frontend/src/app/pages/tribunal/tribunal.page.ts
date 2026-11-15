import { Component, computed, effect, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { CourbeTailleComponent } from '../../components/courbe-taille/courbe-taille.component';
import { PlaidoirieComponent } from '../../components/plaidoirie/plaidoirie.component';
import { Mode, TourDiscussion } from '../../models/proces.model';
import { ApiService } from '../../services/api.service';
import { ProcesService } from '../../services/proces.service';
import { dollars, pct, tonVerdict } from '../../shared/format';

/** Le tribunal : choix du dossier, procès, verdict, salle et pièces du greffier. */
@Component({
  selector: 'rdc-tribunal',
  imports: [RouterLink, PlaidoirieComponent, CourbeTailleComponent],
  templateUrl: './tribunal.page.html',
  styleUrl: './tribunal.page.css',
})
export class TribunalPage {
  readonly tribunal = inject(ProcesService);
  private readonly api = inject(ApiService);

  readonly profilCle = signal('');
  readonly ticker = signal('');
  readonly taille = signal(0.2);
  readonly mode = signal<Mode>('gabarit');
  readonly intentionTexte = signal('');
  readonly explicationIntention = signal('');
  readonly intentionEnCours = signal(false);

  readonly discussionActive = signal(false);
  readonly toursAffiches = signal<TourDiscussion[]>([]);
  private timerDiscussion?: ReturnType<typeof setTimeout>;

  readonly pct = pct;
  readonly dollars = dollars;
  readonly tonVerdict = tonVerdict;

  readonly profil = computed(
    () => this.tribunal.profils().find((p) => p.cle === this.profilCle()) ?? null,
  );

  readonly proces = this.tribunal.resultat;

  readonly motifs = computed(() => {
    const p = this.proces();
    if (!p) return [];
    const d = p.decision;
    return [...d.contraintes, ...d.tensions, ...d.manquants];
  });

  readonly sourceTexte = computed(() => {
    const s = this.tribunal.sante();
    if (!s) return '';
    const donnees = s.source.type === 's3' ? `Amazon S3, bucket ${s.source.bucket}` : 'fichiers locaux';
    return `Données : ${donnees} · Région AWS : ${s.source.region}`;
  });

  constructor() {
    const persona = inject(ActivatedRoute).snapshot.queryParamMap.get('persona');
    this.tribunal.chargerReferentiels();
    effect(() => {
      const profils = this.tribunal.profils();
      if (profils.length && !this.profilCle()) {
        const profil = profils.find((p) => p.cle === persona) ?? profils[0];
        this.choisirProfil(profil.cle);
      }
    });

    // Déclenche l'animation progressive dès qu'un procès avec discussion arrive
    effect(() => {
      const pr = this.proces();
      if (pr?.discussion && pr.discussion.length > 0) {
        this.demarrerAnimationDiscussion(pr.discussion);
      } else {
        if (this.timerDiscussion) {
          clearTimeout(this.timerDiscussion);
        }
        this.discussionActive.set(false);
        this.toursAffiches.set([]);
      }
    });
  }

  demarrerAnimationDiscussion(tours: TourDiscussion[]): void {
    if (!tours || tours.length === 0) {
      this.discussionActive.set(false);
      this.toursAffiches.set([]);
      return;
    }
    if (this.timerDiscussion) {
      clearTimeout(this.timerDiscussion);
    }
    this.discussionActive.set(true);
    this.toursAffiches.set([]);
    let index = 0;

    const jouerProchainTour = () => {
      if (index < tours.length) {
        const tour = tours[index];
        this.toursAffiches.update((liste) => [...liste, tour]);
        const pause = tour.pause_ms || 2200;
        index++;
        this.timerDiscussion = setTimeout(jouerProchainTour, pause);
      } else {
        this.discussionActive.set(false);
      }
    };

    jouerProchainTour();
  }

  passerAnimation(): void {
    if (this.timerDiscussion) {
      clearTimeout(this.timerDiscussion);
      this.timerDiscussion = undefined;
    }
    const pr = this.proces();
    if (pr?.discussion) {
      this.toursAffiches.set(pr.discussion);
    }
    this.discussionActive.set(false);
  }

  rejouerDiscussion(): void {
    const pr = this.proces();
    if (pr?.discussion) {
      this.demarrerAnimationDiscussion(pr.discussion);
    }
  }

  choisirProfil(cle: string): void {
    const profil = this.tribunal.profils().find((p) => p.cle === cle);
    if (!profil) return;
    this.profilCle.set(cle);
    this.ticker.set(profil.demandeExemple.ticker);
    this.taille.set(profil.demandeExemple.taille);
    this.explicationIntention.set('');
    if (this.timerDiscussion) {
      clearTimeout(this.timerDiscussion);
    }
    this.toursAffiches.set([]);
    this.discussionActive.set(false);
    this.tribunal.effacer();
  }

  choisirTicker(ticker: string): void {
    this.ticker.set(ticker);
  }

  choisirTaille(valeur: string): void {
    this.taille.set(Number(valeur));
  }

  choisirMode(mode: Mode): void {
    this.mode.set(mode);
  }

  ouvrir(): void {
    if (!this.profilCle() || !this.ticker()) return;
    this.tribunal.ouvrir({
      profil: this.profilCle(),
      ticker: this.ticker(),
      taille: this.taille(),
      mode: this.mode(),
      intention_texte: this.intentionTexte() || undefined,
    });
  }

  mettreAJourIntention(event: Event): void {
    this.intentionTexte.set((event.target as HTMLInputElement).value);
  }

  analyserIntention(): void {
    const texte = this.intentionTexte().trim();
    if (!texte || !this.profilCle()) return;
    this.intentionEnCours.set(true);
    this.api.interpreterIntention(this.profilCle(), texte).subscribe({
      next: (res) => {
        this.ticker.set(res.ticker);
        this.taille.set(res.taille);
        this.explicationIntention.set(res.explication);
        this.intentionEnCours.set(false);
      },
      error: () => {
        this.intentionEnCours.set(false);
      },
    });
  }

  choisirArbitrage(choix: 'OUI' | 'NON'): void {
    if (!this.profilCle() || !this.ticker()) return;
    this.tribunal.choisirArbitrage(choix, this.profilCle(), this.ticker(), this.taille());
  }

  demanderScenarios(): void {
    if (!this.profilCle() || !this.ticker()) return;
    this.tribunal.genererScenarios(this.profilCle(), this.ticker(), this.taille(), this.intentionTexte());
  }

  telechargerPdf(choix?: string): void {
    if (!this.profilCle() || !this.ticker()) return;
    this.tribunal.telechargerPdf(
      this.profilCle(),
      this.ticker(),
      this.taille(),
      this.mode(),
      this.intentionTexte(),
      choix
    );
  }

  valeur(event: Event): string {
    return (event.target as HTMLSelectElement).value;
  }
}
