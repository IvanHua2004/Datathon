import { Routes } from '@angular/router';

import { AccueilPage } from './pages/accueil/accueil.page';
import { DuelPage } from './pages/duel/duel.page';
import { GreffierPage } from './pages/greffier/greffier.page';
import { PersonasPage } from './pages/personas/personas.page';
import { RapportComparatifPage } from './pages/rapport-comparatif/rapport-comparatif.page';
import { RapportDuelPage } from './pages/rapport-duel/rapport-duel.page';
import { TribunalPage } from './pages/tribunal/tribunal.page';

export const routes: Routes = [
  { path: '', component: AccueilPage, title: 'Règlement de comptes' },
  { path: 'personas', component: PersonasPage, title: 'Choisis ton persona · Règlement de comptes' },
  { path: 'persona', redirectTo: 'personas' },
  { path: 'question', component: GreffierPage, title: 'Le greffier · Règlement de comptes' },
  { path: 'duel', component: DuelPage, title: 'Le duel · Règlement de comptes' },
  { path: 'tribunal', component: TribunalPage, title: 'Le tribunal · Règlement de comptes' },
  { path: 'tribunal-2', component: TribunalPage, data: { versionScene: true }, title: 'Tribunal 2 · Règlement de comptes' },
  { path: 'rapport-duel', component: RapportDuelPage, title: 'Tableau de bord du duel · Règlement de comptes' },
  { path: 'rapport-comparatif', component: RapportComparatifPage, title: 'Rapport comparatif · Règlement de comptes' },
  { path: '**', redirectTo: '' },
];
