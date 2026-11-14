import { Routes } from '@angular/router';

import { AccueilPage } from './pages/accueil/accueil.page';
import { PersonasPage } from './pages/personas/personas.page';
import { TribunalPage } from './pages/tribunal/tribunal.page';

export const routes: Routes = [
  { path: '', component: AccueilPage, title: 'Règlement de comptes' },
  { path: 'personas', component: PersonasPage, title: 'Choisis ton persona · Règlement de comptes' },
  { path: 'tribunal', component: TribunalPage, title: 'Le tribunal · Règlement de comptes' },
  { path: '**', redirectTo: '' },
];
