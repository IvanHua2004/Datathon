import { DOCUMENT } from '@angular/common';
import { Injectable, inject } from '@angular/core';

const MURMURE_SALLE = 'assets/tribunal-2/voix/weldert-crowd-talking-138493.mp3';

@Injectable({ providedIn: 'root' })
export class SonAudienceService {
  readonly lecteur = inject(DOCUMENT).createElement('audio');

  jouerAmbianceSalle(): Promise<void> {
    const lecteur = this.lecteur;
    if (lecteur.getAttribute('src') !== MURMURE_SALLE) lecteur.src = MURMURE_SALLE;
    lecteur.loop = true;
    lecteur.volume = 0.55;
    lecteur.playbackRate = 1;
    return lecteur.play();
  }

  arreterAmbianceSalle(): void {
    if (this.lecteur.getAttribute('src') === MURMURE_SALLE) this.lecteur.pause();
  }

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
