import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';

import { EnteteComponent } from '../../components/entete/entete.component';
import { PiecesMonnaieComponent } from '../../components/pieces-monnaie/pieces-monnaie.component';
import { cleConversation, cleRetour, effacer } from '../../shared/memoire';
import { ConfigurationPersona, NiveauRisque, Profil } from '../../models/proces.model';
import { ApiService } from '../../services/api.service';
import { ProcesService } from '../../services/proces.service';

/** Simulation réservée aux adultes : pas de persona de moins de 18 ans. */
const AGE_MINIMUM = 18;
const MESSAGE_AGE = 'Le persona doit avoir au moins 18 ans.';

@Component({
  selector: 'rdc-personas',
  imports: [EnteteComponent, PiecesMonnaieComponent],
  // Le bandeau du parcours (logo + étapes) au-dessus de la page.
  styles: `
    :host { display: grid; grid-template-rows: auto minmax(0, 1fr); grid-template-columns: minmax(0, 1fr); height: 100dvh; }
    .custom-form, .custom-form label { display: grid; gap: 0.375rem; }
    .custom-form { gap: 0.65rem; }
    .custom-portrait { position: relative; }
    .custom-summary { display: grid; gap: 0.5rem; }
    .custom-summary, .custom-title { overflow-wrap: anywhere; }
    .custom-note { white-space: pre-wrap; }
    .custom-portfolio { margin: 0; font-size: 0.8rem; line-height: 1.35; }
    .custom-portfolio strong { color: #fec946; }
    .custom-portfolio.vague { color: #d9b9c6; font-style: italic; }
    .custom-hint { margin: 0; color: #d9b9c6; font-size: 0.78rem; line-height: 1.35; }
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
              <rdc-pieces-monnaie />
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
              @if (portefeuilleNote(); as positions) {
                <p class="custom-portfolio"><strong>Portefeuille :</strong> {{ positions }}</p>
              } @else {
                <p class="custom-portfolio vague">Positions non précisées : les agents raisonneront sur un portefeuille de référence fictif.</p>
              }
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
            <label>Âge (18 ans minimum)
              <input name="age" type="number" min="18" max="120" step="1" [attr.value]="configuration()?.age" required
                (input)="verifierAge($any($event.target))">
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
              <textarea name="note" rows="3" maxlength="200" aria-describedby="custom-note-hint"
                placeholder="Ex. SPY 60 %, XBB.TO 40 %. Je préfère éviter la crypto."
                [defaultValue]="configuration()?.note ?? ''"></textarea>
            </label>
            <p id="custom-note-hint" class="custom-hint">Indique tes positions avec leur part (au total environ 100 %) pour que les agents parlent de ton portefeuille. Sinon, ils utiliseront un portefeuille de référence fictif.</p>
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
  /** Le persona enregistré pendant cette visite de la page : la carte repart vide à chaque chargement. */
  private readonly enregistre = signal<Profil | undefined>(undefined);
  readonly configuration = computed<ConfigurationPersona | undefined>(() => this.enregistre()?.configuration);
  /** Positions lues dans la note, ou null si la note ne les décrit pas assez. */
  readonly portefeuilleNote = computed(() => {
    const p = this.enregistre();
    if (!p || p.portefeuilleDeclare === false) return null;
    return p.portefeuille.map((x) => `${x.ticker} ${Math.round(x.poids * 100)} %`).join(', ');
  });
  readonly riskLabels: Record<NiveauRisque, string> = {
    faible: 'Faible',
    faible_a_modere: 'Faible à modéré',
    modere: 'Modéré',
    modere_a_eleve: 'Modéré à élevé',
    eleve: 'Élevé',
  };
  readonly riskLevels = Object.keys(this.riskLabels) as NiveauRisque[];
  readonly selectionDuration = 180;

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

  constructor() {
    // Chaque arrivée sur cette page repart de zéro : le persona personnalisé précédent est oublié
    // partout (cookie du serveur, liste des profils, conversation du greffier).
    this.oublierPersonnalise();
    this.api.oublierPersona().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({ error: () => undefined });
  }

  private oublierPersonnalise(): void {
    this.tribunal.personaPersonnalise.set(null);
    effacer(cleConversation('personnalise'));
    effacer(cleRetour('personnalise'));
  }

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

  /** Message en français à la place de celui du navigateur : le persona doit être majeur. */
  verifierAge(champ: HTMLInputElement): void {
    champ.setCustomValidity(champ.value !== '' && Number(champ.value) < AGE_MINIMUM ? MESSAGE_AGE : '');
  }

  savePersona(event: Event, dialog: HTMLDialogElement, form: HTMLFormElement): void {
    event.preventDefault();
    if (this.saving()) return;
    const values = new FormData(form);
    const horizon_min = Number(values.get('horizon_min'));
    const horizon_max = Number(values.get('horizon_max'));
    if (Number(values.get('age')) < AGE_MINIMUM) {
      this.saveError.set(MESSAGE_AGE);
      return;
    }
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
          // Nouveau persona : le greffier recommence une conversation neuve avec lui.
          this.oublierPersonnalise();
          this.tribunal.personaPersonnalise.set(persona);
          this.enregistre.set(persona);
          this.saving.set(false);
          dialog.close();
          // Le persona qu'on vient de configurer reste sélectionné, prêt à confirmer.
          this.selectedPersona.set('personnalise');
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
