import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { Actif, DemandeProces, Proces, Profil, Sante } from '../models/proces.model';
import { AnalyseQuestion, DemandeAnalyse } from '../models/question.model';

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

  analyserQuestion(demande: DemandeAnalyse): Observable<AnalyseQuestion> {
    return this.http.post<AnalyseQuestion>(`${this.base}/questions/analyser`, demande);
  }

  ouvrirProces(demande: DemandeProces): Observable<Proces> {
    return this.http.post<Proces>(`${this.base}/proces`, demande);
  }
}
