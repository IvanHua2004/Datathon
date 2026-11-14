import { Component } from '@angular/core';
import { bootstrapApplication } from '@angular/platform-browser';

import { AppComponent } from './app/app.component';
import { appConfig } from './app/app.config';
@Component({
  selector: 'rdc-menu',
  template: `
    <header class="creators">
      <span>Inès Mameri</span>
      <span>Ivan Hua</span>
      <span>Margot-Loane Salmon--Cottreau</span>
      <span>Marilyn Ngoc Huyen Phung</span>
    </header>
    @if (showPersonas) {
      <main class="menu persona-page">
        <a class="menu-back" href="./">← Retour au menu</a>
        <h1>Choisis ton persona</h1>
        <div class="persona-grid">
          @for (persona of personas; track persona.id) {
            <article class="persona-card">
              <h2>{{ persona.name }}</h2>
              <p class="persona-details">{{ persona.age }} ans · {{ persona.risk }}<br>Horizon de {{ persona.horizon }}</p>
              <p>{{ persona.summary }}</p>
              <a class="start" [href]="'http://localhost:8501/?persona=' + persona.id">Choisir {{ persona.name }}</a>
            </article>
          }
        </div>
      </main>
    } @else {
      <main class="menu">
        <div class="menu-accents" aria-hidden="true">
          @for (accent of accents; track $index) {
            <span
              [style.left.%]="accent.x"
              [style.top.%]="accent.y"
              [style.--angle]="accent.angle + 'deg'"
              [style.animation-delay.s]="accentDelays[$index]"
              (animationiteration)="moveAccent($index)"
            ></span>
          }
        </div>
        <h1 class="logo" aria-label="Règlement de comptes">
          <img class="logo-title" src="assets/logo_reglements_de.png" alt="" width="738" height="242">
          <img class="logo-comptes" src="assets/logo_comptes.png" alt="" width="624" height="136">
        </h1>
        <a class="start" href="?page=personas">Débuter</a>
        <img class="judge-runner" src="assets/juge-course.gif" alt="" width="443" height="443">
      </main>
    }
  `,
})
class MenuComponent {
  readonly showPersonas = new URLSearchParams(window.location.search).get('page') === 'personas';
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
  readonly accentDelays = [0.5, 0.85, 3.2, 5.3, 5.75];
  readonly accents = this.accentDelays.map(() => this.randomAccent());

  moveAccent(index: number): void {
    this.accents[index] = this.randomAccent();
  }

  private randomAccent() {
    // The empty outer band leaves the logo, button and running judge clear.
    const y = 7 + Math.random() * 69;
    const outerWidth = y < 19 ? 42 : 16;
    const offset = 4 + Math.random() * outerWidth;

    return {
      x: Math.random() < 0.5 ? offset : 100 - offset,
      y,
      angle: Math.round(Math.random() * 360),
    };
  }
}

bootstrapApplication(AppComponent, appConfig).catch(console.error);
