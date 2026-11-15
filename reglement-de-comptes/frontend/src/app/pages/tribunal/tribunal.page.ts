import { Component, computed, effect, inject, input, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { Mode } from '../../models/proces.model';

import { CourbeTailleComponent } from '../../components/courbe-taille/courbe-taille.component';
import { PlaidoirieComponent } from '../../components/plaidoirie/plaidoirie.component';
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
  private readonly router = inject(Router);

  readonly profilCle = signal('');
  readonly ticker = signal('');
  readonly taille = signal(0.2);
  /** Paramètres d'URL envoyés par la page du greffier : /tribunal?profil=…&ticker=…&taille=…&question=… */
  readonly profilDemande = input<string>('', { alias: 'profil' });
  readonly tickerDemande = input<string>('', { alias: 'ticker' });
  readonly tailleDemande = input<string>('', { alias: 'taille' });
  readonly question = input<string>('');
  private demandeLancee = false;
  /** Bedrock seulement (« Sans modèle » retiré de l'interface). */
  readonly mode = signal<Mode>('bedrock');
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
    const persona = inject(ActivatedRoute).snapshot.queryParamMap.get('persona');
    this.tribunal.chargerReferentiels();
    effect(() => {
      const profils = this.tribunal.profils();
      if (!profils.length || this.profilCle()) return;
      const demande = profils.find((p) => p.cle === this.profilDemande());
      const taille = Number(this.tailleDemande());
      if (demande && this.tickerDemande() && taille > 0 && !this.demandeLancee) {
        // Arrivée depuis le greffier : le procès s'ouvre tout seul.
        this.demandeLancee = true;
        this.profilCle.set(demande.cle);
        this.ticker.set(this.tickerDemande());
        this.taille.set(taille);
        this.ouvrir();
      } else {
        // Arrivée depuis la page des personas : /tribunal?persona=robert
        const profil = profils.find((p) => p.cle === persona) ?? profils[0];
        this.choisirProfil(profil.cle);
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

  /** Pour l'instant, « Ouvrir le procès » mène au greffier (maquette C) avec le persona choisi. */
  versGreffier(): void {
    if (!this.profilCle()) return;
    this.router.navigate(['/question'], { queryParams: { profil: this.profilCle() } });
  }

  ouvrir(): void {
    if (!this.profilCle() || !this.ticker()) return;
    this.tribunal.ouvrir({
      profil: this.profilCle(),
      ticker: this.ticker(),
      taille: this.taille(),
      mode: this.mode(),
      intention_texte: this.intentionTexte() || this.question() || undefined,
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
