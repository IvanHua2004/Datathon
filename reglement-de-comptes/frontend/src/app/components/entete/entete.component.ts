import { Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { Profil } from '../../models/proces.model';

/** Bandeau commun aux pages du parcours : logo (retour au menu) et étapes. */
@Component({
  selector: 'rdc-entete',
  imports: [RouterLink],
  templateUrl: './entete.component.html',
  styleUrl: './entete.component.scss',
})
export class EnteteComponent {
  readonly etape = input.required<number>();
  readonly persona = input<Pick<Profil, 'cle' | 'nom'> | null>(null);
  readonly etapes = ['Persona', 'Question', 'Débat', 'Verdict'];
}
