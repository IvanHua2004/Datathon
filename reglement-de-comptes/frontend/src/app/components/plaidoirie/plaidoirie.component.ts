import { Component, input } from '@angular/core';

import { Plaidoirie } from '../../models/proces.model';

/** Une plaidoirie (Défense ou Procureur) avec le contrôle du greffier. */
@Component({
  selector: 'rdc-plaidoirie',
  template: `
    <article class="carte">
      <h2>{{ plaidoirie().role }}</h2>
      @if (plaidoirie().temoins_convoques.length) {
        <p class="temoins">Témoins convoqués : {{ plaidoirie().temoins_convoques.join(', ') }}</p>
      }
      <p class="texte">{{ plaidoirie().texte }}</p>
      @if (plaidoirie().non_verifies.length) {
        <p class="greffier greffier--alerte" role="status">
          Greffier : chiffres absents des pièces → {{ plaidoirie().non_verifies.join(', ') }}
        </p>
      } @else {
        <p class="greffier">Greffier : tous les chiffres cités figurent dans les pièces.</p>
      }
    </article>
  `,
  styles: `
    :host { display: block; min-width: 0; }
    .carte {
      height: 100%;
      background: #fff8ec;
      color: #200e0c;
      border: 1px solid #e8d9c4;
      border-radius: 10px;
      padding: 1.25rem 1.4rem;
      display: flex;
      flex-direction: column;
      gap: 0.6rem;
    }
    h2 { margin: 0; font-size: 1.2rem; }
    .temoins { margin: 0; font-size: 0.85rem; color: #5c4a55; }
    .texte { margin: 0; line-height: 1.6; }
    .greffier { margin: auto 0 0; font-size: 0.85rem; color: #1e6b38; }
    .greffier--alerte { color: #a3261a; font-weight: 600; }
  `,
})
export class PlaidoirieComponent {
  readonly plaidoirie = input.required<Plaidoirie>();
}
