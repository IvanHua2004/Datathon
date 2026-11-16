import { Component, computed, input } from '@angular/core';

import { Profil } from '../../models/proces.model';
import { VoteEnregistre } from '../../shared/memoire';
import { NIVEAUX, profilRevele } from '../../shared/profil-revele';

/**
 * « Votre profil d'après vos choix » : tous les votes de la session, relus avec une règle fixe,
 * placent l'investisseur sur la même échelle de risque que son persona de départ.
 */
@Component({
  selector: 'rdc-profil-revele',
  templateUrl: './profil-revele.component.html',
  styleUrl: './profil-revele.component.scss',
})
export class ProfilReveleComponent {
  readonly profil = input.required<Profil>();
  readonly votes = input<readonly VoteEnregistre[]>([]);

  readonly niveaux = NIVEAUX;
  readonly bilan = computed(() => profilRevele(this.profil(), this.votes()));
  readonly titre = computed(() => {
    const b = this.bilan();
    const nom = this.profil().nom;
    if (b.fiabilite === 'aucune') return 'Pas encore assez de votes pour tirer un profil';
    if (b.ecart === 0) return `Vos choix sont alignés avec le profil de ${nom}`;
    return b.ecart > 0
      ? `Vos choix sont plus audacieux que le profil de ${nom}`
      : `Vos choix sont plus prudents que le profil de ${nom}`;
  });
  readonly lecture = computed(() => {
    const b = this.bilan();
    const declare = NIVEAUX[b.declare].libelle.toLowerCase();
    const revele = NIVEAUX[b.revele].libelle.toLowerCase();
    if (b.fiabilite === 'aucune') {
      return 'Rendez votre verdict dans un procès ou un duel : chaque vote sera relu ici, face au profil choisi au départ.';
    }
    if (b.ecart === 0) return `Persona choisi : risque ${declare}. Vos votes le confirment.`;
    return `Persona choisi : risque ${declare}. D'après vos votes, vous vous comportez plutôt comme un profil à risque ${revele}.`;
  });
  readonly libelleFiabilite = computed(() => {
    const n = this.bilan().indices.filter((i) => i.compte).length;
    switch (this.bilan().fiabilite) {
      case 'aucune': return 'Aucun vote';
      case 'faible': return 'Indice faible · 1 vote';
      case 'indicative': return `Indicatif · ${n} votes`;
      default: return `Solide · ${n} votes`;
    }
  });
}
