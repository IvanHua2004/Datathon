import { Component, DestroyRef, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

@Component({
  selector: 'rdc-personas',
  template: `
    <main class="menu persona-page">
      <h1>Choisis ton <span>persona</span></h1>
      <div class="persona-grid">
        @for (persona of personas; track persona.id) {
          <a class="persona-card" [href]="'/tribunal?persona=' + persona.id"
            [class.persona-selected]="selectedPersona() === persona.id"
            [style.--selection-duration]="selectionDuration + 'ms'"
            [attr.aria-label]="'Choisir ' + persona.name"
            (click)="choosePersona($event, persona.id)">
            <img class="persona-portrait" [src]="'assets/' + persona.id + '.png'" alt="" width="1254" height="1254">
            <h2>{{ persona.name }}</h2>
            <p class="persona-details">{{ persona.age }} ans · {{ persona.risk }}<br>Horizon de {{ persona.horizon }}</p>
            <p>{{ persona.summary }}</p>
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
          </a>
        }
      </div>
    </main>
  `,
})
export class PersonasPage {
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  private navigationTimer?: ReturnType<typeof setTimeout>;

  readonly selectedPersona = signal('');
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

  constructor() {
    this.destroyRef.onDestroy(() => clearTimeout(this.navigationTimer));
  }

  choosePersona(event: MouseEvent, persona: string): void {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) {
      return;
    }
    event.preventDefault();
    if (this.selectedPersona()) return;

    const openTribunal = () => {
      void this.router.navigate(['/tribunal'], { queryParams: { persona } }).finally(() => {
        this.selectedPersona.set('');
      });
    };

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      openTribunal();
      return;
    }

    this.selectedPersona.set(persona);
    const lastCoinDelay = Math.max(...this.coins.map((coin) => coin.delay));
    this.navigationTimer = setTimeout(
      openTribunal,
      this.selectionDuration + this.coinDuration + lastCoinDelay,
    );
  }
}
