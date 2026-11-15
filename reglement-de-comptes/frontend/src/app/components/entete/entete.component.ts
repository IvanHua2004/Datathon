import { Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';

/** Bandeau commun aux pages du parcours : logo (retour au menu) et étapes. */
@Component({
  selector: 'rdc-entete',
  imports: [RouterLink],
  template: `
    <header class="entete">
      <a routerLink="/" class="marque" aria-label="Règlement de comptes, retour au menu">
        <img src="assets/logo-parcours.png" alt="" width="738" height="738">
      </a>
      <ol class="etapes" aria-label="Étapes">
        @for (e of etapes; track e; let i = $index) {
          <li [class.faite]="i + 1 < etape()" [class.courante]="i + 1 === etape()"
              [attr.aria-current]="i + 1 === etape() ? 'step' : null">
            <span class="numero" aria-hidden="true">{{ i + 1 < etape() ? '✓' : i + 1 }}</span>
            {{ e }}
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
    .marque {
      position: relative;
      display: block;
      flex: none;
      width: 6.5rem;
      height: 3.9rem;
      overflow: hidden;
      border-radius: 2px;
    }
    .marque img {
      position: absolute;
      top: 50%;
      display: block;
      width: 100%;
      height: auto;
      transform: translateY(-50%);
    }
    .marque:focus-visible { outline: 3px solid #fff; outline-offset: 4px; }
    .etapes {
      list-style: none;
      margin: 0;
      padding: 0;
      display: flex;
      gap: 1.25rem;
      font-size: 0.875rem;
      flex: 1 1 auto;
      min-width: 0;
    }
    .etapes li {
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.4rem;
      padding: 0.35rem 0.75rem;
      border-radius: 3px;
      border: 2px solid rgb(255 229 191 / 40%);
      color: rgb(255 229 191 / 75%);
    }
    .etapes li:not(:last-child)::after {
      position: absolute;
      top: 50%;
      left: calc(100% + 0.25rem);
      width: 0.85rem;
      color: #e7ccd9;
      font-size: 1rem;
      line-height: 1;
      text-align: center;
      transform: translateY(-50%);
      content: '›';
    }
    .numero { min-width: 1ch; font-weight: 700; text-align: center; }
    .etapes li.faite { border-color: rgb(255 229 191 / 60%); color: #ffe5bf; }
    .etapes li.courante { background: #ffc247; border-color: #ffc247; color: #200e0c; font-weight: 700; }

    @media (max-width: 520px) {
      .etapes {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        flex-basis: 100%;
        gap: 0.75rem;
        font-size: 0.75rem;
      }
      .etapes li { flex-direction: column; gap: 0.125rem; padding-inline: 0; }
      .etapes li:not(:last-child)::after { left: 100%; width: 0.95rem; }
    }
  `,
})
export class EnteteComponent {
  readonly etape = input.required<number>();
  readonly etapes = ['Persona', 'Question', 'Débat', 'Verdict'];
}
