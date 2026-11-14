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
      <div class="actions-group">
        <a class="start" href="http://localhost:8501">Débuter le Tribunal</a>
       
      </div>
      <img class="judge-runner" src="assets/juge-course.gif" alt="" width="443" height="443">
    </main>
  `,
})
class MenuComponent {
  readonly accentDelays = [0.5, 0.85, 3.2, 5.3, 5.75];
  readonly accents = this.accentDelays.map(() => this.randomAccent());
}

bootstrapApplication(AppComponent, appConfig).catch(console.error);
