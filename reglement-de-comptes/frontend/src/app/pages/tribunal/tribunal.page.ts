import { Component, computed, effect, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { CourbeTailleComponent } from '../../components/courbe-taille/courbe-taille.component';
import { PlaidoirieComponent } from '../../components/plaidoirie/plaidoirie.component';
import { Mode } from '../../models/proces.model';
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

  readonly profilCle = signal('');
  readonly ticker = signal('');
  readonly taille = signal(0.2);
  readonly mode = signal<Mode>('gabarit');
  readonly intentionTexte = signal('');

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
    this.tribunal.chargerReferentiels();
    // Premier profil sélectionné dès que les référentiels arrivent.
    effect(() => {
      const profils = this.tribunal.profils();
      if (profils.length && !this.profilCle()) {
        this.choisirProfil(profils[0].cle);
      }
    });
  }

  choisirProfil(cle: string): void {
    const profil = this.tribunal.profils().find((p) => p.cle === cle);
    if (!profil) return;
    this.profilCle.set(cle);
    this.ticker.set(profil.demandeExemple.ticker);
    this.taille.set(profil.demandeExemple.taille);
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
