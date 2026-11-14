import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { Actif, AnalyseComparative, DemandeProces, IntentionResultat, Mode, Proces, Profil, Sante, ScenarioAlternatif } from '../models/proces.model';

/** Accès HTTP à l'API Python. Les chemins sont relatifs : nginx (ou ng serve) relaie /api/. */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api';

  sante(): Observable<Sante> {
    return this.http.get<Sante>(`${this.base}/sante`);
  }

  profils(): Observable<Profil[]> {
    return this.http.get<Profil[]>(`${this.base}/profils`);
  }

  actifs(): Observable<Actif[]> {
    return this.http.get<Actif[]>(`${this.base}/actifs`);
  }

  tailles(): Observable<number[]> {
    return this.http.get<number[]>(`${this.base}/tailles`);
  }

  ouvrirProces(demande: DemandeProces): Observable<Proces> {
    return this.http.post<Proces>(`${this.base}/proces`, demande);
  }

  interpreterIntention(profil: string, texte: string): Observable<IntentionResultat> {
    return this.http.post<IntentionResultat>(`${this.base}/intention`, { profil, texte });
  }

  comparerDecision(profil: string, ticker: string, taille: number, choix_investisseur: 'OUI' | 'NON'): Observable<AnalyseComparative> {
    return this.http.post<AnalyseComparative>(`${this.base}/comparaison`, { profil, ticker, taille, choix_investisseur });
  }

  demanderScenarios(profil: string, ticker: string, taille: number, intention_texte?: string): Observable<ScenarioAlternatif[]> {
    return this.http.post<ScenarioAlternatif[]>(`${this.base}/scenarios`, { profil, ticker, taille, intention_texte });
  }

  telechargerPdf(profil: string, ticker: string, taille: number, mode: Mode, intention_texte?: string, choix_investisseur?: string): Observable<Blob> {
    return this.http.post(`${this.base}/pdf`, { profil, ticker, taille, mode, intention_texte, choix_investisseur }, {
      responseType: 'blob',
    });
  }
}
