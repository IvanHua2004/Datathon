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
  templateUrl: './personas.page.html',
  styleUrl: './personas.page.scss',
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
