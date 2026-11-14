import { Routes } from '@angular/router';

import { AccueilPage } from './pages/accueil/accueil.page';
import { GreffierPage } from './pages/greffier/greffier.page';
import { PersonaPage } from './pages/persona/persona.page';
import { TribunalPage } from './pages/tribunal/tribunal.page';

export const routes: Routes = [
  { path: '', component: AccueilPage, title: 'Règlement de comptes' },
  { path: 'persona', component: PersonaPage, title: 'Choisis ton persona · Règlement de comptes' },
  { path: 'question', component: GreffierPage, title: 'Le greffier · Règlement de comptes' },
  { path: 'tribunal', component: TribunalPage, title: 'Le tribunal · Règlement de comptes' },
  { path: '**', redirectTo: '' },
];
