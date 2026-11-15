import { HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { forkJoin } from 'rxjs';

import { Actif, AnalyseComparative, DemandeProces, Mode, Proces, Profil, Sante, ScenarioAlternatif } from '../models/proces.model';
import { AudienceDossier } from '../models/question.model';
import { ApiService } from './api.service';

/** État du tribunal partagé par les pages : référentiels, procès en cours, erreurs. */
@Injectable({ providedIn: 'root' })
export class ProcesService {
  private readonly api = inject(ApiService);

  private readonly profilsReference = signal<Profil[]>([]);
  readonly personaPersonnalise = signal<Profil | null>(null);
  readonly profils = computed(() => {
    const reference = this.profilsReference();
    const personnalise = this.personaPersonnalise();
    return reference.length && personnalise ? [...reference, personnalise] : reference;
  });
  readonly actifs = signal<Actif[]>([]);
  readonly tailles = signal<number[]>([]);
  readonly sante = signal<Sante | null>(null);

  readonly chargement = signal(false);
  readonly enCours = signal(false);
  /** Le dernier procès plaidé. Il reste en mémoire pour revenir voter sans relancer les avocats. */
  readonly resultat = signal<Proces | null>(null);
  /** Le camp retenu par l'investisseur pour ce procès, ou null tant qu'il n'a pas voté. */
  readonly voteAudience = signal<'avocat_defense' | 'procureur' | null>(null);
  readonly erreur = signal<string | null>(null);

  readonly comparaison = signal<AnalyseComparative | null>(null);
  readonly chargementComparaison = signal(false);

  readonly scenarios = signal<ScenarioAlternatif[] | null>(null);
  readonly chargementScenarios = signal(false);

  readonly chargementPdf = signal(false);
  readonly succesPdf = signal(false);

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
        this.personaPersonnalise.update((p) => p ?? r.profils.find((profil) => profil.cle === 'personnalise') ?? null);
        this.profilsReference.set(r.profils.filter((profil) => profil.cle !== 'personnalise'));
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
        this.voteAudience.set(null);
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
    if (this.chargementPdf()) {
      return;
    }
    this.chargementPdf.set(true);
    this.succesPdf.set(false);
    this.api.telechargerPdf(profil, ticker, taille, mode, intentionTexte, choix).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `jugement_tribunal_${profil}_${ticker}.pdf`;
        a.click();
        window.URL.revokeObjectURL(url);
        this.chargementPdf.set(false);
        this.succesPdf.set(true);
        setTimeout(() => this.succesPdf.set(false), 3500);
      },
      error: (e: unknown) => {
        this.erreur.set(this.message(e));
        this.chargementPdf.set(false);
        this.succesPdf.set(false);
      },
    });
  }

  /** Le procès en mémoire correspond-il à cette demande ? (pour le reprendre au lieu de le relancer) */
  correspond(profil: string, ticker: string, taille: number): boolean {
    const d = this.resultat()?.demande;
    return !!d && d.profil === profil && d.ticker === ticker && Math.abs(d.taille - taille) < 1e-9;
  }

  /** Le dossier de l'audience plaidée pour ce persona, envoyé à l'archiviste avec les questions. */
  dossierAudience(profil: string): AudienceDossier | undefined {
    const pr = this.resultat();
    if (!pr || pr.demande.profil !== profil || !pr.pieces.length) return undefined;
    return {
      ticker: pr.demande.ticker,
      nomTitre: pr.demande.nomTitre,
      taille: pr.demande.taille,
      pieces: pr.pieces.map(({ numero, temoin, description, faits, source, periode, limites }) =>
        ({ numero, temoin, description, faits, source, periode, limites })),
      plaidoiries: pr.plaidoiries.slice(0, 2).map((p, i) => ({
        camp: i === 0 ? 'defense' : 'accusation',
        texte: p.texte,
        nonVerifies: p.non_verifies ?? [],
      })),
    };
  }

  effacer(): void {
    this.voteAudience.set(null);
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
