import { Component, inject, input, signal } from '@angular/core';

import { Plaidoirie, ReponseAnalogie } from '../../models/proces.model';
import { ApiService } from '../../services/api.service';

/** Une plaidoirie (Défense ou Procureur) avec le contrôle du greffier. */
@Component({
  selector: 'rdc-plaidoirie',
  templateUrl: './plaidoirie.component.html',
  styleUrl: './plaidoirie.component.scss',
})
export class PlaidoirieComponent {
  readonly plaidoirie = input.required<Plaidoirie>();
  private readonly api = inject(ApiService);
  readonly affichee = signal(false);
  readonly enCours = signal(false);
  readonly analogie = signal<ReponseAnalogie | null>(null);

  basculerAnalogie(): void {
    if (this.affichee() && this.analogie()) {
      this.affichee.set(false);
      return;
    }
    if (this.analogie()) {
      this.affichee.set(true);
      return;
    }
    this.enCours.set(true);
    this.affichee.set(true);
    this.api.demanderAnalogie({
      texte: this.plaidoirie().texte,
      role: this.plaidoirie().role,
      mode: 'bedrock',
    }).subscribe({
      next: (rep) => {
        this.analogie.set(rep);
        this.enCours.set(false);
      },
      error: () => {
        this.analogie.set({
          analogie: "Voyez cela comme une traversée en mer : par vent fort, mieux vaut vérifier que les gilets et amarres sont solides avant d'accélérer.",
          titre: "L'analogie du juré",
          source: 'secours',
        });
        this.enCours.set(false);
      },
    });
  }
}
