import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

/** Page d'accueil : le menu animé (styles dans src/styles.css, sélecteur rdc-menu). */
@Component({
  selector: 'rdc-menu',
  imports: [RouterLink],
  template: `
    <header class="creators">
      <span>Inès Mameri</span>
      <span>Ivan Hua</span>
      <span>Margot-Loane Salmon--Cottreau</span>
      <span>Marilyn Ngoc Huyen Phung</span>
    </header>
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
      <a class="start" routerLink="/personas">Débuter</a>
      <ul class="menu-intro" role="list">
        <li>Posez vos questions</li>
        <li>Assistez aux débats entre deux avocats</li>
        <li>Rendez votre verdict</li>
        <li>Découvrez si vos décisions reflètent vraiment votre profil d’investisseur</li>
      </ul>
      <img class="judge-runner" src="assets/juge-course.gif" alt="" width="443" height="443">
    </main>
  `,
})
export class AccueilPage {
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
