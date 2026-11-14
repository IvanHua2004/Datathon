import { Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';

/** Bandeau commun aux pages du parcours : logo (retour au menu) et étapes. */
@Component({
  selector: 'rdc-entete',
  imports: [RouterLink],
  template: `
    <header class="entete">
      <a routerLink="/" class="marque" aria-label="Règlement de comptes, retour au menu">
        <img class="marque-haut" src="assets/logo_reglements_de.png" alt="" width="738" height="242">
        <img class="marque-bas" src="assets/logo_comptes.png" alt="" width="624" height="136">
      </a>
      <ol class="etapes" aria-label="Étapes">
        @for (e of etapes; track e; let i = $index) {
          <li [class.faite]="i + 1 < etape()" [class.courante]="i + 1 === etape()"
              [attr.aria-current]="i + 1 === etape() ? 'step' : null">
            <span aria-hidden="true">{{ i + 1 < etape() ? '✓' : i + 1 }}</span> {{ e }}
          </li>
        }
      </ol>
      <ng-content />
    </header>
  `,
  styles: `
    .entete {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.6rem 1.5rem;
      padding: 0.6rem clamp(1rem, 3vw, 1.5rem);
      background: #773c6f;
      color: #ffe5bf;
    }
    .marque { display: inline-flex; flex-direction: column; align-items: center; border-radius: 2px; }
    .marque img { height: auto; display: block; }
    .marque-haut { width: 8rem; }
    .marque-bas { width: 6.5rem; margin-top: -0.35rem; }
    .marque:focus-visible { outline: 3px solid #fff; outline-offset: 4px; }
    .etapes {
      list-style: none;
      margin: 0;
      padding: 0;
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
      font-size: 0.875rem;
      flex: 1 1 auto;
      min-width: 0;
    }
    .etapes li {
      padding: 0.3rem 0.75rem;
      border-radius: 999px;
      border: 1px solid rgb(255 229 191 / 30%);
      color: rgb(255 229 191 / 75%);
    }
    .etapes li.faite { border-color: rgb(255 229 191 / 60%); color: #ffe5bf; }
    .etapes li.courante { background: #ffc247; border-color: #ffc247; color: #200e0c; font-weight: 700; }
  `,
})
export class EnteteComponent {
  readonly etape = input.required<number>();
  readonly etapes = ['Persona', 'Question', 'Débat', 'Verdict'];
}
