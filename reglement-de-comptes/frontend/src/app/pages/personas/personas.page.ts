import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';

import { EnteteComponent } from '../../components/entete/entete.component';
import { ConfigurationPersona, NiveauRisque } from '../../models/proces.model';
import { ApiService } from '../../services/api.service';
import { ProcesService } from '../../services/proces.service';

@Component({
  selector: 'rdc-personas',
  imports: [EnteteComponent],
  // Le bandeau du parcours (logo + étapes) au-dessus de la page.
  styles: `
    :host { display: grid; grid-template-rows: auto minmax(0, 1fr); grid-template-columns: minmax(0, 1fr); height: 100dvh; }
    .custom-form, .custom-form label { display: grid; gap: 0.375rem; }
    .custom-form { gap: 0.65rem; }
    .custom-portrait { position: relative; }
    .custom-summary { display: grid; gap: 0.5rem; }
    .custom-summary, .custom-title { overflow-wrap: anywhere; }
    .custom-note { white-space: pre-wrap; }
    .card-select {
      position: absolute;
      z-index: 1;
      inset: 0;
      width: 100%;
      border: 0;
      border-radius: inherit;
      background: transparent;
      cursor: pointer;
    }
    .card-select:focus-visible { outline: 2px solid #e9ca91; outline-offset: 4px; }
    .custom-button.confirm-persona { align-self: center; min-width: 9rem; background: var(--confirm-background); color: #fff; }
    .confirm-persona:hover:enabled { background: var(--confirm-background-hover); }
    @media (prefers-reduced-motion: reduce) {
      .persona-card.persona-selected { animation: none; }
      .persona-coins { display: none; }
    }
    .custom-dialog {
      box-sizing: border-box;
      width: min(25rem, calc(100% - 2rem));
      max-height: calc(100dvh - 2rem);
      padding: 1.25rem;
      border: 1px solid #967687;
      border-radius: 0.5rem;
      background: #3b2836;
      color: #feedd3;
    }
    .custom-dialog::backdrop { background: rgb(0 0 0 / 65%); }
    .custom-dialog h2 { margin: 0 0 1rem; color: #fec946; overflow-wrap: anywhere; }
    .custom-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 0.5rem; }
    .custom-form .custom-cancel { background: transparent; color: #feedd3; }
    .custom-form label { font-size: 0.875rem; }
    .custom-form :is(input, select, textarea) {
      box-sizing: border-box;
      width: 100%;
      padding: 0.45rem 0.55rem;
      border: 1px solid #967687;
      border-radius: 0.25rem;
      background: #21101d;
      color: #feedd3;
      font: inherit;
    }
    .custom-form textarea { resize: vertical; }
    .custom-button {
      align-self: start;
      padding: 0.65rem;
      border: 0;
      border-radius: 0.25rem;
      background: #fec946;
      color: #21101d;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      text-align: center;
      text-decoration: none;
    }
    .custom-edit {
      position: absolute;
      z-index: 2;
      inset: 0.5rem 0.5rem auto auto;
      display: grid;
      place-items: center;
      width: 2.25rem;
      height: 2.25rem;
      padding: 0;
      border: 1px solid #967687;
      border-radius: 50%;
      background: #21101d;
      color: #fec946;
      cursor: pointer;
    }
    .custom-horizon {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 0.5rem;
      min-width: 0;
      margin: 0;
      padding: 0.5rem;
      border: 1px solid #967687;
      border-radius: 0.25rem;
      font-size: 0.875rem;
    }
    :is(.custom-button, .custom-edit):disabled { opacity: 0.65; cursor: wait; }
    .custom-edit:focus,
    :is(.custom-button, .custom-form :is(input, select, textarea)):focus-visible {
      outline: 2px solid #fec946;
      outline-offset: 2px;
    }
  `,
  template: `
    <rdc-entete [etape]="1" />
    <main class="menu persona-page">
      <h1>Choisis ton <span>persona</span></h1>
      <div class="persona-grid">
        @for (persona of personas; track persona.id) {
          <article class="persona-card"
            [class.persona-selected]="selectedPersona() === persona.id"
            [style.--selection-duration]="selectionDuration + 'ms'">
            <button class="card-select" type="button" [attr.aria-label]="'Sélectionner ' + persona.name"
              [attr.aria-describedby]="'persona-summary-' + persona.id"
              [attr.aria-pressed]="selectedPersona() === persona.id" (click)="selectedPersona.set(persona.id)"></button>
            <img class="persona-portrait" [src]="'assets/' + persona.id + '.png'" alt="" width="1254" height="1254">
            <h2>{{ persona.name }}</h2>
            <p class="persona-details">{{ persona.age }} ans · {{ persona.risk }}<br>Horizon de {{ persona.horizon }}</p>
            <p class="persona-summary" [id]="'persona-summary-' + persona.id">{{ persona.summary }}</p>
            @if (selectedPersona() === persona.id) {
              <span class="persona-coins" [style.--coin-duration]="coinDuration + 'ms'" aria-hidden="true">
                @for (coin of coins; track $index) {
                  <span class="persona-coin"
                    [style.--coin-x]="coin.x + '%'"
                    [style.--coin-y]="coin.y + '%'"
                    [style.--coin-drift]="coin.drift + 'px'"
                    [style.--coin-spin]="coin.spin + 'deg'"
                    [style.--coin-delay]="coin.delay + 'ms'">$</span>
                }
              </span>
            }
          </article>
        }
        <article class="persona-card" aria-labelledby="custom-card-title"
          [class.persona-selected]="selectedPersona() === 'personnalise'"
          [style.--selection-duration]="selectionDuration + 'ms'">
          <div class="custom-portrait">
            <img class="persona-portrait" src="assets/personnalise.png" alt="" width="1254" height="1254">
            <button #editPersona class="custom-edit" type="button" aria-label="Modifier le persona personnalisé"
              title="Modifier le persona" (click)="openPersonaForm(details, customForm)">
              <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor"
                stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="m16 4 4 4M4 20l4-.8L20 7a2.8 2.8 0 0 0-4-4L4 15z" />
              </svg>
            </button>
          </div>
          <h2 id="custom-card-title" class="custom-title">{{ configuration()?.nom ?? 'Personnalisé' }}</h2>
          @if (configuration(); as config) {
            <button class="card-select" type="button" [attr.aria-label]="'Sélectionner ' + config.nom"
              [attr.aria-pressed]="selectedPersona() === 'personnalise'"
              (click)="selectedPersona.set('personnalise')"></button>
            <div class="custom-summary">
              <p class="persona-details">{{ config.age }} ans · Risque {{ riskLabels[config.risque].toLowerCase() }}<br>Horizon de {{ config.horizon_min }}{{ config.horizon_max !== config.horizon_min ? ' à ' + config.horizon_max : '' }} ans
              </p>
              @if (config.note) { <p class="custom-note">{{ config.note }}</p> }
            </div>
          } @else {
            <button class="card-select" type="button" aria-label="Repérer le bouton de configuration du persona personnalisé"
              (click)="highlightEditButton(editPersona)"></button>
          }
        </article>
      </div>
      <button class="custom-button confirm-persona" type="button" [disabled]="!selectedPersona() || confirming()"
        (click)="confirmPersona()">Confirmer</button>
      <dialog #details class="custom-dialog" aria-labelledby="custom-persona-title"
        (cancel)="saving() && $event.preventDefault()">
          <h2 id="custom-persona-title">Configurer le persona</h2>
          <form #customForm class="custom-form" (submit)="savePersona($event, details, customForm)">
            <label>Nom du persona
              <input name="nom" type="text" maxlength="50" pattern=".*\\S.*"
                [attr.value]="configuration()?.nom ?? ''" required autofocus>
            </label>
            <label>Âge (ans)
              <input name="age" type="number" min="1" max="120" step="1" [attr.value]="configuration()?.age" required>
            </label>
            <label>Niveau de risque
              <select name="risque" required>
                <option value="" disabled [attr.selected]="configuration() ? null : ''">Sélectionner</option>
                @for (level of riskLevels; track level) {
                  <option [value]="level" [attr.selected]="configuration()?.risque === level ? '' : null">{{ riskLabels[level] }}</option>
                }
              </select>
            </label>
            <fieldset class="custom-horizon">
              <legend>Horizon (ans)</legend>
              <label>Minimum
                <input name="horizon_min" type="number" min="1" max="100" step="1" [attr.value]="configuration()?.horizon_min" required>
              </label>
              <label>Maximum
                <input name="horizon_max" type="number" min="1" max="100" step="1" [attr.value]="configuration()?.horizon_max" required>
              </label>
            </fieldset>
            <label>Note (facultative)
              <textarea name="note" rows="2" maxlength="200" placeholder="Ex. Je préfère éviter la crypto."
                [defaultValue]="configuration()?.note ?? ''"></textarea>
            </label>
            <div class="custom-actions">
              <button type="button" class="custom-button custom-cancel" [disabled]="saving()" (click)="details.close()">Annuler</button>
              <button class="custom-button" type="submit" [disabled]="saving()">
                {{ saving() ? 'Enregistrement…' : 'Enregistrer' }}
              </button>
            </div>
            @if (saveError()) {
              <p role="alert">{{ saveError() }}</p>
            }
          </form>
      </dialog>
    </main>
  `,
})
export class PersonasPage {
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  private readonly api = inject(ApiService);
  private readonly tribunal = inject(ProcesService);
  private editHintAnimation?: Animation;

  readonly selectedPersona = signal('');
  readonly confirming = signal(false);
  readonly saving = signal(false);
  readonly saveError = signal('');
  readonly configuration = signal<ConfigurationPersona | undefined>(undefined);
  readonly riskLabels: Record<NiveauRisque, string> = {
    faible: 'Faible',
    faible_a_modere: 'Faible à modéré',
    modere: 'Modéré',
    modere_a_eleve: 'Modéré à élevé',
    eleve: 'Élevé',
  };
  readonly riskLevels = Object.keys(this.riskLabels) as NiveauRisque[];
  readonly selectionDuration = 180;
  readonly coinDuration = 940;
  readonly coins = [
    { x: 4, y: 16, drift: -13, spin: -36, delay: 0 },
    { x: 14, y: 4, drift: -9, spin: 29, delay: 27 },
    { x: 29, y: -1, drift: 8, spin: -58, delay: 11 },
    { x: 67, y: 2, drift: 12, spin: 31, delay: 46 },
    { x: 88, y: 8, drift: 17, spin: 69, delay: 0 },
    { x: 97, y: 26, drift: 13, spin: -32, delay: 34 },
    { x: 99, y: 44, drift: 9, spin: 52, delay: 18 },
    { x: 2, y: 47, drift: -12, spin: -44, delay: 56 },
    { x: 5, y: 68, drift: -8, spin: 33, delay: 71 },
    { x: 94, y: 73, drift: 13, spin: -41, delay: 79 },
  ];

  readonly personas = [
    {
      id: 'amira',
      name: 'Amira',
      age: 26,
      risk: 'Risque élevé',
      horizon: '15 ans ou plus',
      summary: 'Elle vise la croissance et s’intéresse aux technologies émergentes et aux cryptoactifs, tout en gardant un portefeuille diversifié.',
    },
    {
      id: 'mateo',
      name: 'Mateo',
      age: 41,
      risk: 'Risque modéré',
      horizon: '8 à 12 ans',
      summary: 'Il cherche un équilibre entre croissance et stabilité, et accorde une grande importance aux critères ESG.',
    },
    {
      id: 'robert',
      name: 'Robert',
      age: 59,
      risk: 'Risque faible à modéré',
      horizon: '3 à 5 ans',
      summary: 'Il privilégie la stabilité et la préservation de son capital, mais une occasion très médiatisée peut le tenter.',
    },
  ];

  highlightEditButton(button: HTMLButtonElement): void {
    button.focus({ preventScroll: true });
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    this.editHintAnimation?.cancel();
    this.editHintAnimation = button.animate(
      ['0', '-4px', '4px', '-2px', '2px', '0'].map((x) => ({ transform: `translateX(${x})` })),
      { duration: 360, easing: 'ease-out' },
    );
  }

  openPersonaForm(dialog: HTMLDialogElement, form: HTMLFormElement): void {
    if (this.saving() || this.confirming()) return;
    this.saveError.set('');
    form.reset();
    dialog.showModal();
  }

  savePersona(event: Event, dialog: HTMLDialogElement, form: HTMLFormElement): void {
    event.preventDefault();
    if (this.saving()) return;
    const values = new FormData(form);
    const horizon_min = Number(values.get('horizon_min'));
    const horizon_max = Number(values.get('horizon_max'));
    if (horizon_min > horizon_max) {
      this.saveError.set('L’horizon maximal doit être au moins égal à l’horizon minimal.');
      return;
    }
    this.saving.set(true);
    this.saveError.set('');

    this.api.enregistrerPersona({
      nom: String(values.get('nom')).trim(),
      age: Number(values.get('age')),
      risque: values.get('risque') as NiveauRisque,
      horizon_min,
      horizon_max,
      note: String(values.get('note')).trim(),
    })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (persona) => {
          this.tribunal.personaPersonnalise.set(persona);
          this.configuration.set(persona.configuration);
          this.saving.set(false);
          dialog.close();
        },
        error: () => {
          this.saveError.set('Impossible d’enregistrer le persona. Réessaie dans un instant.');
          this.saving.set(false);
        },
      });
  }

  confirmPersona(): void {
    const profil = this.selectedPersona();
    if (!profil || this.confirming()) return;
    this.confirming.set(true);
    void this.router.navigate(['/question'], { queryParams: { profil } })
      .finally(() => this.confirming.set(false));
  }
}
