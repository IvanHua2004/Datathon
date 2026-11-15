import { DOCUMENT } from '@angular/common';
import { Injectable, inject } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class SonAudienceService {
  readonly lecteur = inject(DOCUMENT).createElement('audio');

  amorcer(): void {
    // Le même lecteur reçoit ensuite les voix, même après un changement de page.
    if (!this.lecteur.paused) return;
    this.lecteur.loop = false;
    this.lecteur.src = 'assets/tribunal-2/voix/silence.wav';
    void this.lecteur.play().catch(() => {
      // Le bouton haut-parleur reste disponible si le navigateur refuse la lecture.
    });
  }
}
