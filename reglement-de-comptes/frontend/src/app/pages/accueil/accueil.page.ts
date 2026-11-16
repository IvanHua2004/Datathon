import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

/** Page d'accueil : le menu animé (styles dans src/styles.scss, sélecteur rdc-menu). */
@Component({
  selector: 'rdc-menu',
  imports: [RouterLink],
  templateUrl: './accueil.page.html',
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
