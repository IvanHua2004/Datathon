import { HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { forkJoin } from 'rxjs';

import { Actif, AnalyseComparative, DemandeProces, Mode, Proces, Profil, Sante, ScenarioAlternatif } from '../models/proces.model';
import { ApiService } from './api.service';

/** État du tribunal partagé par les pages : référentiels, procès en cours, erreurs. */
@Injectable({ providedIn: 'root' })
export class ProcesService {
  private readonly api = inject(ApiService);

  readonly profils = signal<Profil[]>([]);
  readonly actifs = signal<Actif[]>([]);
  readonly tailles = signal<number[]>([]);
  readonly sante = signal<Sante | null>(null);

  readonly chargement = signal(false);
  readonly enCours = signal(false);
  readonly resultat = signal<Proces | null>(null);
  readonly erreur = signal<string | null>(null);

  readonly comparaison = signal<AnalyseComparative | null>(null);
  readonly chargementComparaison = signal(false);

  readonly scenarios = signal<ScenarioAlternatif[] | null>(null);
  readonly chargementScenarios = signal(false);

  chargerReferentiels(): void {
    if (this.profils().length || this.chargement()) {
      return;
    }
    this.chargement.set(true);
    this.erreur.set(null);
    forkJoin({
      profils: this.api.profils(),
      actifs: this.api.actifs(),
      tailles: this.api.tailles(),
      sante: this.api.sante(),
    }).subscribe({
      next: (r) => {
        this.profils.set(r.profils);
        this.actifs.set(r.actifs);
        this.tailles.set(r.tailles);
        this.sante.set(r.sante);
        this.chargement.set(false);
      },
      error: (e: unknown) => {
        this.erreur.set(this.message(e));
        this.chargement.set(false);
      },
    });
  }

  ouvrir(demande: DemandeProces): void {
    this.enCours.set(true);
    this.erreur.set(null);
    this.comparaison.set(null);
    this.scenarios.set(null);
    this.api.ouvrirProces(demande).subscribe({
      next: (proces) => {
        this.resultat.set(proces);
        this.enCours.set(false);
      },
      error: (e: unknown) => {
        this.erreur.set(this.message(e));
        this.enCours.set(false);
      },
    });
  }

  choisirArbitrage(choix: 'OUI' | 'NON', profil: string, ticker: string, taille: number): void {
    this.chargementComparaison.set(true);
    this.api.comparerDecision(profil, ticker, taille, choix).subscribe({
      next: (comp) => {
        this.comparaison.set(comp);
        this.chargementComparaison.set(false);
      },
      error: (e: unknown) => {
        this.erreur.set(this.message(e));
        this.chargementComparaison.set(false);
      },
    });
  }

  genererScenarios(profil: string, ticker: string, taille: number, intentionTexte?: string): void {
    this.chargementScenarios.set(true);
    this.api.demanderScenarios(profil, ticker, taille, intentionTexte).subscribe({
      next: (scenarios) => {
        this.scenarios.set(scenarios);
        this.chargementScenarios.set(false);
      },
      error: (e: unknown) => {
        this.erreur.set(this.message(e));
        this.chargementScenarios.set(false);
      },
    });
  }

  telechargerPdf(profil: string, ticker: string, taille: number, mode: Mode, intentionTexte?: string, choix?: string): void {
    this.api.telechargerPdf(profil, ticker, taille, mode, intentionTexte, choix).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `jugement_tribunal_${profil}_${ticker}.pdf`;
        a.click();
        window.URL.revokeObjectURL(url);
      },
      error: (e: unknown) => {
        this.erreur.set(this.message(e));
      },
    });
  }

  effacer(): void {
    this.resultat.set(null);
    this.comparaison.set(null);
    this.scenarios.set(null);
  }

  private message(e: unknown): string {
    if (e instanceof HttpErrorResponse) {
      if (e.status === 0) {
        return "L'API du tribunal ne répond pas. Vérifiez qu'elle est lancée (port 8000 en développement).";
      }
      const detail = typeof e.error?.detail === 'string' ? e.error.detail : e.message;
      return `Erreur ${e.status} : ${detail}`;
    }
    return String(e);
  }
}
