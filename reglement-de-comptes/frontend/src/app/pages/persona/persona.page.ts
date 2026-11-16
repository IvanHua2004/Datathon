import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

import { EnteteComponent } from '../../components/entete/entete.component';
import { ProcesService } from '../../services/proces.service';
import { dollars, pct } from '../../shared/format';

/** Étape 1 : choisir l'investisseur fictif dont on va juger la décision. */
@Component({
  selector: 'rdc-persona',
  imports: [RouterLink, EnteteComponent],
  templateUrl: './persona.page.html',
  styleUrl: './persona.page.scss',
})
export class PersonaPage {
  readonly tribunal = inject(ProcesService);
  readonly pct = pct;
  readonly dollars = dollars;

  constructor() {
    this.tribunal.chargerReferentiels();
  }
}
