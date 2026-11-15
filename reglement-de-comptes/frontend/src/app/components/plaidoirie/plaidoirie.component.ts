import { Component, inject, input, signal } from '@angular/core';

import { Plaidoirie, ReponseAnalogie } from '../../models/proces.model';
import { ApiService } from '../../services/api.service';

/** Une plaidoirie (Défense ou Procureur) avec le contrôle du greffier. */
@Component({
  selector: 'rdc-plaidoirie',
  template: `
    <article class="carte">
      <div class="entete-carte">
        <h2>{{ plaidoirie().role }}</h2>
        <button type="button" class="bouton-analogie"
          [class.actif]="affichee() && !!analogie()"
          [class.chargement]="enCours()"
          (click)="basculerAnalogie()"
          title="Obtenir une analogie vulgarisée pour cette plaidoirie">
          <span>💡</span> {{ enCours() ? 'Vulgarisation…' : (affichee() && !!analogie() ? 'Masquer' : 'Une analogie ?') }}
        </button>
      </div>
      @if (plaidoirie().temoins_convoques.length) {
        <p class="temoins">Témoins convoqués : {{ plaidoirie().temoins_convoques.join(', ') }}</p>
      }
      <p class="texte">{{ plaidoirie().texte }}</p>
      @if (affichee()) {
        @if (enCours()) {
          <div class="encart-analogie en-cours">
            <em>💡 L'Interprète du Juré cherche une analogie…</em>
          </div>
        } @else if (analogie(); as rep) {
          <div class="encart-analogie">
            <div class="titre-juré">
              <strong>💡 {{ rep.titre || "L'analogie du juré" }}</strong>
              <button type="button" class="fermer" (click)="affichee.set(false)" aria-label="Fermer">×</button>
            </div>
            <p class="texte-analogie">{{ rep.analogie }}</p>
          </div>
        }
      }
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
    .entete-carte {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.5rem;
    }
    h2 { margin: 0; font-size: 1.2rem; }
    .bouton-analogie {
      display: inline-flex;
      align-items: center;
      gap: 0.3rem;
      padding: 0.2rem 0.6rem;
      border: 1px solid #c9a463;
      border-radius: 9999px;
      background: #fff;
      color: #633e08;
      font: inherit;
      font-size: 0.78rem;
      font-weight: 700;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .bouton-analogie:hover {
      background: #fdf0d2;
      border-color: #a87e35;
    }
    .bouton-analogie.actif {
      background: #eedcb3;
      border-color: #8c6523;
    }
    .encart-analogie {
      padding: 0.65rem 0.85rem;
      border: 1px solid #e0c896;
      border-left: 3px solid #d49a37;
      border-radius: 0.35rem;
      background: #fffcf4;
      color: #382414;
      font-size: 0.88rem;
      margin: 0.2rem 0;
    }
    .encart-analogie.en-cours {
      font-style: italic;
      color: #7d6b56;
    }
    .titre-juré {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 0.25rem;
      color: #7a4e10;
    }
    .fermer {
      background: transparent;
      border: none;
      font-size: 1.1rem;
      cursor: pointer;
      color: #8c735d;
      padding: 0 0.2rem;
    }
    .texte-analogie {
      margin: 0;
      line-height: 1.5;
    }
    .temoins { margin: 0; font-size: 0.85rem; color: #5c4a55; }
    .texte { margin: 0; line-height: 1.6; }
    .greffier { margin: auto 0 0; font-size: 0.85rem; color: #1e6b38; }
    .greffier--alerte { color: #a3261a; font-weight: 600; }
  `,
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
