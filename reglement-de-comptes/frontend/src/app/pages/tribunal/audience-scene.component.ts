import { Component, DestroyRef, ElementRef, afterNextRender, afterRenderEffect, computed, effect, inject, input, linkedSignal, output, signal, viewChild } from '@angular/core';
import { Piece, Position, Proces, TourDiscussion } from '../../models/proces.model';
import { RapportAudienceComponent } from './rapport-audience.component';
import { SonAudienceService } from '../../services/son-audience.service';
import { choisirVoixAudience } from './voix-audience';

const MS_PAR_MOT = 230;
const FIN_DE_PHRASE = /[.!?…][»”"]?\s*$/u;
const PAUSE_COURTE = /[,;:][»”"]?\s*$/u;
const PHRASES = new Intl.Segmenter('fr', { granularity: 'sentence' });
type Camp = 'avocat_defense' | 'procureur';

function motsDe(texte: string): string[] {
  return texte.match(/\S+\s*/gu) ?? [];
}

const PERSONNAGES = [
  { role: 'avocat_defense', image: 'assets/tribunal-2/defense', emplacement: 'gauche', nom: 'Me Vigor', cote: 'La Défense' },
  { role: 'juge', image: 'assets/tribunal-2/juge', emplacement: 'centre' },
  { role: 'procureur', image: 'assets/tribunal-2/procureur', emplacement: 'droite', nom: 'Me Austère', cote: 'Le Procureur' },
] as const;

@Component({
  selector: 'rdc-audience-scene',
  imports: [RapportAudienceComponent],
  styleUrl: './audience-scene.component.css',
  template: `
    <section class="scene" aria-label="Audience du Tribunal 2">
      <div #ancrageSon hidden></div>
      <div class="plateau">
        @if (tour() && !verdictRendu()) {
          <button class="bouton-verdict" type="button" aria-haspopup="dialog"
            [class.verdict-attendu]="audienceTerminee() && !verdictOuvert()"
            [class.verdict-enfonce]="impactVerdict()" (click)="ouvrirVerdict(fenetreVerdict)">
            Verdict
            @if (impactVerdict()) {
              <span class="eclats-verdict" aria-hidden="true">
                <i></i><i></i><i></i><i></i><i></i><i></i>
              </span>
            }
          </button>
        }
        @for (personnage of personnages; track personnage.role) {
          <div class="personnage" aria-hidden="true" [attr.data-emplacement]="personnage.emplacement"
            [class.parle]="lectureActive() && tour()?.role === personnage.role">
            @if (personnage.role !== 'juge') {
              <span class="nom-avocat"><strong>{{ personnage.nom }}</strong><span>{{ personnage.cote }}</span></span>
            }
            <picture>
              <source media="(prefers-reduced-motion: reduce)" [srcset]="personnage.image + '.png'">
              <img [src]="personnage.image + (lectureActive() && tour()?.role === personnage.role ? '.gif' : '.png')" alt="">
            </picture>
          </div>
        }
      </div>
      @if (tour(); as tour) {
        <article class="dialogue" [class.verdict-final]="verdictRendu()">
          <div class="portrait" aria-hidden="true">
            @if (portrait(); as image) {
              <img [src]="image" [class.miroir]="tour.role === 'procureur'" alt="">
            } @else {
              <span>{{ tour.avatar }}</span>
            }
          </div>
          <div class="replique" #replique tabindex="0" aria-live="polite">
            <div class="etiquettes">
              <h3>{{ tour.acteur }}</h3>
              @if (tour.piece) { <span class="piece">Pièce {{ tour.piece }}</span> }
            </div>
            <p class="titre-replique">{{ tour.titre }}</p>
            <p class="texte-accessible">{{ tour.texte }}</p>
            <p class="texte-replique" aria-hidden="true">
              @for (mot of mots(); track $index) {
                <span [class.mot-masque]="!texteIntegral() && $index > motActif()"
                  [class.mot-actif]="lectureActive() && $index === motActif()">{{ mot }}</span>
              }
            </p>
            @if (tour.non_verifies?.length) {
              <p class="alerte"><strong>Audit du greffier.</strong> Chiffres absents des pièces scellées : {{ tour.non_verifies.join(', ') }}</p>
            }
          </div>
          <nav class="commandes" aria-label="Parcourir les interventions">
            <div class="options-lecture">
              <button type="button" [attr.aria-label]="libelleLecture()" [title]="libelleLecture()" (click)="basculerLecture()">
                <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  @if (audienceTerminee() || annonceTerminee()) {
                    <path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"
                      d="M4 5v5h5M4.5 10a8 8 0 1 1 .8 7"/>
                  } @else if (lectureAuto()) {
                    <path d="M7 5h4v14H7zm6 0h4v14h-4z"/>
                  } @else {
                    <path d="M8 5v14l11-7z"/>
                  }
                </svg>
              </button>
              <button type="button" [attr.aria-label]="sonActive() && !sonBloque() ? 'Couper le son' : 'Activer le son'"
                [title]="sonActive() && !sonBloque() ? 'Couper le son' : 'Activer le son'" (click)="basculerSon()">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
                  stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M11 5 6 9H3v6h3l5 4z"/>
                  @if (sonActive() && !sonBloque()) {
                    <path d="M14.5 8.5a5 5 0 0 1 0 7M17.5 5.5a9 9 0 0 1 0 13"/>
                  } @else {
                    <path d="m15 9 6 6m0-6-6 6"/>
                  }
                </svg>
              </button>
            </div>
            @if (!verdictRendu()) {
              <span class="compteur" aria-label="Intervention">{{ index() + 1 }} / {{ tours().length }}</span>
            }
            <div class="progression">
              @if (verdictRendu()) {
                @if (annonceTerminee()) {
                  <span class="compteur">Audience levée</span>
                } @else {
                  <button type="button" class="suivant" (click)="motActif.set(mots().length)">Afficher tout le verdict</button>
                }
              } @else {
                <button type="button" (click)="afficherTour(index() - 1)" [disabled]="index() === 0">← Précédent</button>
                @if (index() < tours().length - 1) {
                  <button type="button" class="suivant"
                    [title]="repliqueDevoilee() ? 'Passer à la réplique suivante' : 'Afficher toute la réplique'"
                    (click)="suivant()">Suivant →</button>
                } @else if (!audienceTerminee()) {
                  <button type="button" class="suivant" (click)="motActif.set(mots().length)">Terminer la lecture</button>
                } @else {
                  <span class="compteur">À vous de trancher</span>
                }
              }
            </div>
          </nav>
        </article>
      } @else {
        <div class="dialogue attente">
          <h2>Salle d’audience</h2>
          <p>{{ enCours() ? 'Les parties préparent leurs interventions…' : 'Soumettez une question au greffier pour commencer l’audience.' }}</p>
        </div>
      }
    </section>
    <dialog #fenetreVerdict class="fenetre-verdict" aria-labelledby="titre-verdict" (close)="verdictOuvert.set(false)">
      <div class="contenu-verdict">
        <header>
          <h2 id="titre-verdict" tabindex="-1" autofocus>À vous de rendre le verdict</h2>
          <button class="fermer-verdict" type="button" aria-label="Fermer le résumé" (click)="fenetreVerdict.close()">×</button>
        </header>
        <div class="plaidoiries-verdict">
          @for (camp of plaidoiries(); track camp.role) {
            <section class="camp-verdict">
              <h3>{{ camp.cote }}</h3>
              <p class="nom-camp">{{ camp.nom }}</p>
              <p class="extrait-camp">{{ camp.extrait || 'Plaidoirie indisponible.' }}</p>
              <button type="button" class="bouton-vote" [disabled]="!camp.extrait"
                [attr.aria-pressed]="vote() === camp.role" (click)="vote.set(camp.role)">
                {{ camp.role === 'avocat_defense' ? 'Voter pour la défense' : 'Voter pour l’accusation' }}
              </button>
            </section>
          }
        </div>
        <footer>
          <p role="status">{{ vote() ? 'Confirmez votre choix pour clore l’audience.' : 'Choisissez le camp que vous retenez.' }}</p>
          <button type="button" class="rendre-verdict" [disabled]="!vote()"
            (click)="rendreVerdict(fenetreVerdict)">Rendre mon verdict</button>
        </footer>
      </div>
    </dialog>
    <dialog #fenetreRapport class="fenetre-rapport" aria-labelledby="titre-rapport" (close)="rapportOuvert.set(false)"
      (click)="$event.target === fenetreRapport && fenetreRapport.close()">
      <div class="contenu-rapport">
        <header class="entete-rapport">
          <h2 id="titre-rapport" tabindex="-1" autofocus>Rapport d’analyse</h2>
          <button class="fermer-verdict" type="button" aria-label="Fermer le rapport" (click)="fenetreRapport.close()">×</button>
        </header>
        <div class="corps-rapport">
        @if (rapportOuvert()) {
          <rdc-rapport-audience
            [proces]="proces()"
            [interventions]="interventionsLues()"
            [pieces]="pieces()"
            [vote]="verdictRendu()"
            [audienceTerminee]="audienceTerminee() || !!verdictRendu()"
            [portefeuille]="portefeuille()" />
        }
        </div>
      </div>
      @if (rapportOuvert() && proces()) {
        <aside class="outils-rapport" aria-label="Emporter le rapport">
          <button type="button" class="outil-rapport outil-principal" title="Télécharger le rapport en PDF"
            (click)="telecharger.emit(verdictRendu())">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v11m0 0-4.5-4.5M12 15l4.5-4.5M5 19h14"/></svg>
            <span>PDF</span>
          </button>
          <button type="button" class="outil-rapport" title="Imprimer le rapport" (click)="imprimerRapport()">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 9V4h10v5M7 17H5a1 1 0 0 1-1-1v-5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v5a1 1 0 0 1-1 1h-2M7 14h10v6H7z"/></svg>
            <span>Imprimer</span>
          </button>
        </aside>
      }
    </dialog>
  `,
})
export class AudienceSceneComponent {
  readonly tours = input<readonly TourDiscussion[]>([]);
  readonly pieces = input<readonly Piece[]>([]);
  readonly enCours = input(false);
  /** Le procès complet (verdict, courbe, salle…) pour le rapport d'analyse. */
  readonly proces = input<Proces | null>(null);
  /** Le portefeuille actuel de l'investisseur, pour la barre avant / après du rapport. */
  readonly portefeuille = input<readonly Position[]>([]);
  /** Demande de PDF depuis le rapport, avec le camp retenu par l'investisseur. */
  readonly telecharger = output<'avocat_defense' | 'procureur' | null>();
  readonly index = linkedSignal({ source: this.tours, computation: () => 0 });
  readonly tour = computed<TourDiscussion | undefined>(() => this.annonceVerdict() ?? this.tours()[this.index()]);
  readonly mots = computed(() => motsDe(this.tour()?.texte ?? ''));
  readonly motActif = linkedSignal({ source: this.tour, computation: () => 0 });
  readonly texteIntegral = linkedSignal({ source: this.tour, computation: () => false });
  readonly repliqueDevoilee = computed(() => this.texteIntegral() || this.motActif() >= this.mots().length);
  readonly lectureAuto = signal(true);
  readonly sonActive = signal(true);
  readonly sonBloque = signal(false);
  readonly verdictOuvert = signal(false);
  readonly rapportOuvert = signal(false);
  readonly impactVerdict = signal(false);
  readonly vote = linkedSignal<readonly TourDiscussion[], Camp | null>({ source: this.tours, computation: () => null });
  readonly verdictRendu = linkedSignal<readonly TourDiscussion[], Camp | null>({
    source: this.tours, computation: () => null,
  });
  readonly lectureActive = computed(() =>
    !this.verdictOuvert() && !this.rapportOuvert() && this.lectureAuto() && this.motActif() < this.mots().length);
  readonly audienceTerminee = computed(() =>
    !this.verdictRendu() && this.index() === this.tours().length - 1 && this.motActif() >= this.mots().length);
  readonly annonceTerminee = computed(() => !!this.verdictRendu() && this.motActif() >= this.mots().length);
  readonly libelleLecture = computed(() => {
    if (this.annonceTerminee()) return 'Rejouer l’annonce';
    if (this.audienceTerminee()) return 'Rejouer l’audience';
    return this.lectureAuto() ? 'Mettre la lecture en pause' : 'Reprendre la lecture';
  });
  readonly personnages = PERSONNAGES;
  readonly plaidoiries = computed(() => PERSONNAGES.filter((p) => p.role !== 'juge').map((p) => {
    const texte = this.tours().find((tour) => tour.role === p.role)?.texte ?? '';
    const extrait = Array.from(PHRASES.segment(texte)).slice(0, 2).map(({ segment }) => segment).join('').trim();
    return { ...p, extrait };
  }));
  readonly campRetenu = computed(() => this.plaidoiries().find((camp) => camp.role === this.verdictRendu()));
  private readonly annonceVerdict = computed<TourDiscussion | undefined>(() => {
    const camp = this.campRetenu();
    if (!camp) return;
    const cote = camp.role === 'avocat_defense' ? 'la défense' : 'l’accusation';
    return {
      ordre: this.tours().length + 1,
      etape: 'ANNONCE_VERDICT',
      acteur: 'Le juge',
      role: 'juge',
      avatar: '👨‍⚖️',
      titre: 'Votre verdict',
      texte: `J’annonce votre verdict : vous avez tranché en faveur de ${cote}, représentée par ${camp.nom}. L’audience est levée.`,
      pause_ms: 0,
    };
  });
  private readonly motsLus = linkedSignal<readonly TourDiscussion[], ReadonlyMap<number, number>>({
    source: this.tours, computation: () => new Map(),
  });
  readonly interventionsLues = computed(() => {
    const annonce = this.annonceVerdict();
    const tours = annonce ? [...this.tours(), annonce] : this.tours();
    const progression = this.motsLus();
    return tours.filter((tour) => progression.has(tour.ordre)).map((tour) => {
      const mots = motsDe(tour.texte);
      const lus = progression.get(tour.ordre) ?? 0;
      return { tour, extrait: mots.slice(0, lus).join('').trimEnd(), complet: lus >= mots.length };
    });
  });
  readonly piecesLues = computed(() => {
    const numeros = new Set<string>();
    for (const { tour, complet } of this.interventionsLues()) {
      if (!complet) continue;
      if (tour.piece) numeros.add(tour.piece);
      for (const numero of tour.pieces_associees ?? []) numeros.add(numero);
    }
    return this.pieces().filter((piece) => numeros.has(piece.numero));
  });
  readonly portrait = computed(() => {
    const role = this.tour()?.role;
    const personnage = PERSONNAGES.find((p) => p.role === role);
    if (personnage) return personnage.image + '.png';
    return role === 'greffier' ? 'assets/greffier-transparent.png' : null;
  });
  private readonly replique = viewChild<ElementRef<HTMLElement>>('replique');
  private readonly voixAudience = linkedSignal({ source: this.tours, computation: choisirVoixAudience });
  private readonly lecteur = inject(SonAudienceService).lecteur;
  private dernierTourSon?: TourDiscussion;
  private minuterieVerdict?: ReturnType<typeof setTimeout>;
  private readonly ancrageSon = viewChild<ElementRef<HTMLElement>>('ancrageSon');
  private readonly fenetreRapport = viewChild<ElementRef<HTMLDialogElement>>('fenetreRapport');

  constructor() {
    inject(DestroyRef).onDestroy(() => clearTimeout(this.minuterieVerdict));
    afterNextRender(() => this.ancrageSon()?.nativeElement.append(this.lecteur));
    afterRenderEffect(() => {
      if (this.verdictRendu()) this.replique()?.nativeElement.focus({ preventScroll: true });
    });
    effect(() => {
      const tour = this.tour();
      if (!tour) return;
      const lus = this.texteIntegral() ? this.mots().length : Math.min(this.motActif() + 1, this.mots().length);
      this.motsLus.update((progression) => {
        if (lus <= (progression.get(tour.ordre) ?? 0)) return progression;
        return new Map(progression).set(tour.ordre, lus);
      });
    });

    effect((nettoyer) => {
      if (!this.lectureActive()) return;
      const tour = this.tour();
      const mots = this.mots();
      const indexMot = this.motActif();
      const mot = mots[indexMot];
      const pause = FIN_DE_PHRASE.test(mot) ? 160 : PAUSE_COURTE.test(mot) ? 80 : 0;
      const minuterie = setTimeout(() => {
        if (!this.lectureActive() || this.tour() !== tour || this.motActif() !== indexMot) return;
        if (!this.verdictRendu() && indexMot + 1 === mots.length && this.index() < this.tours().length - 1) {
          this.afficherTour(this.index() + 1);
        } else {
          this.motActif.set(indexMot + 1);
        }
      }, MS_PAR_MOT + pause);
      nettoyer(() => clearTimeout(minuterie));
    });

    effect((nettoyer) => {
      if (!this.lectureActive() || !this.sonActive() || this.sonBloque()) return;
      this.jouerVoix();
      nettoyer(() => this.lecteur.pause());
    });

    afterRenderEffect(() => {
      if (!this.lectureActive()) return;
      this.motActif();
      const panneau = this.replique()?.nativeElement;
      const mot = panneau?.querySelector('.mot-actif');
      if (!panneau || !mot) return;
      const bas = mot.getBoundingClientRect().bottom;
      const limite = panneau.getBoundingClientRect().bottom;
      if (bas > limite) panneau.scrollTop += bas - limite + 4;
    });
  }

  suivant(): void {
    if (!this.repliqueDevoilee()) {
      this.motActif.set(this.mots().length);
      return;
    }
    this.afficherTour(this.index() + 1);
  }

  afficherTour(index: number): void {
    if (index < 0 || index >= this.tours().length) return;
    const panneau = this.replique()?.nativeElement;
    if (panneau) panneau.scrollTop = 0;
    this.index.set(index);
    this.motActif.set(0);
    this.texteIntegral.set(!this.lectureAuto());
    this.dernierTourSon = undefined;
  }

  ouvrirVerdict(fenetre: HTMLDialogElement): void {
    if (this.verdictOuvert()) return;
    this.verdictOuvert.set(true);
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      fenetre.showModal();
      return;
    }
    this.impactVerdict.set(true);
    this.minuterieVerdict = setTimeout(() => {
      this.impactVerdict.set(false);
      fenetre.showModal();
    }, 230);
  }

  ouvrirRapport(): void {
    const fenetre = this.fenetreRapport()?.nativeElement;
    if (!fenetre || fenetre.open) return;
    this.rapportOuvert.set(true);
    fenetre.showModal();
  }

  rendreVerdict(fenetre: HTMLDialogElement): void {
    const choix = this.vote();
    if (!choix) return;
    this.verdictRendu.set(choix);
    this.lectureAuto.set(true);
    const panneau = this.replique()?.nativeElement;
    if (panneau) panneau.scrollTop = 0;
    fenetre.close();
    this.verdictOuvert.set(false);
    if (this.sonActive()) {
      this.sonBloque.set(false);
      this.jouerVoix();
    }
  }

  basculerLecture(): void {
    if (this.annonceTerminee()) {
      this.lectureAuto.set(true);
      this.motActif.set(0);
      this.dernierTourSon = undefined;
    } else if (this.audienceTerminee()) {
      this.lectureAuto.set(true);
      this.afficherTour(0);
    } else {
      this.lectureAuto.update((active) => !active);
    }
    if (this.lectureActive() && this.sonActive() && !this.sonBloque()) this.jouerVoix();
  }

  basculerSon(): void {
    if (this.sonActive() && !this.sonBloque()) {
      this.lecteur.pause();
      this.sonActive.set(false);
      return;
    }
    this.sonActive.set(true);
    this.sonBloque.set(false);
    if (this.lectureActive()) this.jouerVoix();
  }

  private jouerVoix(): void {
    const tour = this.tour();
    if (!tour) return;
    const voix = this.voixAudience()[tour.role];
    if (!voix) return;
    const lecteur = this.lecteur;
    if (lecteur.getAttribute('src') !== voix.fichier) lecteur.src = voix.fichier;
    if (tour !== this.dernierTourSon) {
      lecteur.currentTime = 0;
      this.dernierTourSon = tour;
    }
    lecteur.loop = true;
    lecteur.volume = 0.38;
    lecteur.preservesPitch = false;
    lecteur.playbackRate = voix.vitesse;
    void lecteur.play().catch((erreur: DOMException) => {
      if (erreur.name === 'NotAllowedError') this.sonBloque.set(true);
    });
  }

  /** Imprime uniquement le papier du rapport, sections repliées ouvertes. */
  imprimerRapport(): void {
    document.querySelectorAll<HTMLDetailsElement>('.fenetre-rapport details').forEach((d) => (d.open = true));
    document.body.classList.add('impression-rapport');
    const retirer = () => {
      document.body.classList.remove('impression-rapport');
      window.removeEventListener('afterprint', retirer);
    };
    window.addEventListener('afterprint', retirer);
    window.print();
  }
}
