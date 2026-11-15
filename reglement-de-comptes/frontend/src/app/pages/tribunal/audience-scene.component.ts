import { Component, DestroyRef, ElementRef, TemplateRef, afterNextRender, afterRenderEffect, computed, effect, inject, input, linkedSignal, output, signal, viewChild } from '@angular/core';
import { Piece, Position, Proces, ReponseAnalogie, TourDiscussion } from '../../models/proces.model';
import { RapportAudienceComponent, argumentsDe, chiffresCles } from './rapport-audience.component';
import { dollars, pct } from '../../shared/format';
import { ApiService } from '../../services/api.service';
import { SonAudienceService } from '../../services/son-audience.service';
import { choisirVoixAudience } from './voix-audience';

const MS_PAR_MOT = 230;
const MS_PAR_MOT_ANALOGIE = 185;
const DUREE_ANNONCE_MS = 1400;
const FIN_DE_PHRASE = /[.!?…][»”"]?\s*$/u;
const PAUSE_COURTE = /[,;:][»”"]?\s*$/u;
const EXPRESSIONS_A_SOULIGNER = [
  'silence dans la salle', 'silence', 'attention tout le monde', 'attention',
  'objection', 'levez-vous', 'sous serment', 'pièces à conviction', 'la parole vous revient',
].map((expression) => expression.split(' '));
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

const BLOBS = [1, 2, 3, 4, 5, 6, 7, 8, 9];

function clePortrait(tour: TourDiscussion): string {
  return tour.role === 'temoin' ? tour.temoin || tour.acteur : tour.role + ':' + tour.acteur;
}

@Component({
  selector: 'rdc-audience-scene',
  imports: [RapportAudienceComponent],
  styleUrl: './audience-scene.component.css',
  template: `
    <ng-template #boutonVerdict>
      @if (tour() && !verdictRendu()) {
        <button class="bouton-verdict" type="button" aria-haspopup="dialog"
          [class.verdict-attendu]="audienceTerminee() && !finOuverte() && !verdictOuvert()"
          [class.verdict-enfonce]="impactVerdict()" (click)="ouvrirFin(fenetreFin)">
          <img class="icone-verdict" src="assets/tribunal-2/marteau.png" alt="" />
          <span>Terminé</span>
          @if (impactVerdict()) {
            <span class="eclats-verdict" aria-hidden="true">
              <i></i><i></i><i></i><i></i><i></i><i></i>
            </span>
          }
        </button>
      }
    </ng-template>
    <section class="scene" aria-label="Audience du Tribunal 2">
      <div #ancrageSon hidden></div>
      <div class="plateau">
        @for (annonce of annoncesScene(); track annonce.tour) {
          <div class="annonce-scene" [style.--duree-annonce]="dureeAnnonceMs + 'ms'" aria-hidden="true">
            <div class="cartouche-annonce">
              <strong>{{ annonce.titre }}</strong>
              <span>{{ annonce.tour.acteur }}</span>
            </div>
          </div>
        }
        @for (personnage of personnages; track personnage.role) {
          <div class="personnage" aria-hidden="true" [attr.data-emplacement]="personnage.emplacement"
            [class.parle]="lectureActive() && tour()?.role === personnage.role">
            @if (personnage.role !== 'juge') {
              <span class="nom-avocat"><strong>{{ personnage.nom }}</strong><span>{{ personnage.cote }}</span></span>
            }
            <picture>
              <source media="(prefers-reduced-motion: reduce)" [srcset]="personnage.image + '.png'">
              <img [src]="personnage.image + (preparation() || (lectureActive() && tour()?.role === personnage.role) ? '.gif' : '.png')" alt="">
            </picture>
          </div>
        }
      </div>
      @if (tour(); as tour) {
        <article class="dialogue" [class.verdict-final]="verdictRendu()">
          <div class="portrait" aria-hidden="true">
            @if (portrait(); as image) {
              <img [src]="image" [class.miroir]="tour.role === 'procureur'"
                [class.portrait-blob]="blobActif() !== undefined"
                [class.portrait-blob-recadrer]="blobActif() === 7 || blobActif() === 8" alt="">
            } @else {
              <span>{{ tour.avatar }}</span>
            }
          </div>
          <div class="replique" #replique tabindex="0" aria-live="polite">
            <div class="etiquettes">
              <h3>{{ tour.acteur }}</h3>
              @if (tour.piece) { <span class="piece">Pièce {{ tour.piece }}</span> }
              @if (!annonceActive() && tour.role !== 'huissier') {
                <button type="button" class="bouton-analogie"
                  [class.actif]="analogieAffichee() && !!analogieCourante()"
                  [class.chargement]="analogieEnCours()"
                  (click)="basculerAnalogie()"
                  [title]="analogieAffichee() && !!analogieCourante() ? 'Masquer l’analogie' : 'Obtenir une analogie vulgarisée pour cette intervention'">
                  <span class="icone-ampoule" aria-hidden="true">💡</span>
                  <span>{{ analogieEnCours() ? 'Vulgarisation…' : (analogieAffichee() && !!analogieCourante() ? 'Masquer' : 'Une analogie ?') }}</span>
                </button>
              }
            </div>
            <p class="titre-replique">{{ tour.titre }}</p>
            @if (!annonceActive()) {
              <p class="texte-accessible">{{ tour.texte }}</p>
              <p class="texte-replique" aria-hidden="true">
                @for (mot of mots(); track $index) {
                  <span [class.mot-masque]="!texteIntegral() && $index > motActif()"
                    [class.mot-emphase]="motsEnGras().has($index)"
                    [class.mot-actif]="lectureActive() && $index === motActif()">{{ mot }}</span>
                }
              </p>
              @if (tour.non_verifies?.length) {
                <p class="alerte"><strong>Audit du greffier.</strong> Chiffres absents des pièces scellées : {{ tour.non_verifies.join(', ') }}</p>
              }
              @if (analogieAffichee()) {
                @if (analogieEnCours()) {
                  <aside class="encart-analogie en-chargement" aria-live="polite">
                    <div class="entete-analogie">
                      <span class="icone-analogie" aria-hidden="true">💡</span>
                      <strong>L’Interprète du Juré cherche une analogie…</strong>
                    </div>
                    <p class="texte-chargement">Traduction du jargon en métaphore concrète de la vie courante…</p>
                  </aside>
                } @else if (analogieCourante(); as rep) {
                  <aside class="encart-analogie" aria-live="polite"
                    (click)="devoilerAnalogieComplete()"
                    [title]="!analogieFinieDeLire() ? 'Cliquer pour dévoiler toute l’analogie immédiatement' : ''">
                    <div class="entete-analogie">
                      <div class="titre-juré">
                        <span class="icone-analogie" aria-hidden="true">💡</span>
                        <strong>{{ rep.titre || "L'analogie du juré" }}</strong>
                        @if (!analogieFinieDeLire()) {
                          <span class="badge-lecture">Lecture en cours…</span>
                        } @else {
                          <span class="badge-lecture badge-termine">Terminée</span>
                        }
                      </div>
                      <button type="button" class="fermer-analogie" (click)="fermerAnalogie(); $event.stopPropagation()" aria-label="Fermer l'analogie">×</button>
                    </div>
                    <p class="texte-analogie">
                      @for (mot of motsAnalogie(); track $index) {
                        <span [class.mot-masque]="$index > motAnalogieActif()">{{ mot }}</span>
                      }
                    </p>
                    @if (analogieFinieDeLire()) {
                      <div class="pied-analogie">
                        <button type="button" class="bouton-continuer" (click)="continuerApresAnalogie(); $event.stopPropagation()">
                          Reprendre l’audience →
                        </button>
                      </div>
                    }
                  </aside>
                }
              }
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
                  <button type="button" class="suivant" [disabled]="annonceActive()"
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
        <div class="dialogue attente" [class.attente-active]="preparation()">
          <div>
            <h2>Salle d’audience</h2>
            <p role="status">{{ preparation() ? 'Les parties préparent leurs interventions…' : 'Soumettez une question au greffier pour commencer l’audience.' }}</p>
          </div>
          @if (preparation()) {
            <button class="son-preparation" type="button" (click)="basculerSon()">
              {{ sonActive() && !sonBloque() ? 'Couper l’ambiance' : 'Activer l’ambiance' }}
            </button>
          }
        </div>
      }
    </section>
    <dialog #fenetreFin class="fenetre-fin" aria-labelledby="titre-fin"
      (close)="finOuverte.set(false)" (click)="$event.target === fenetreFin && fenetreFin.close()">
      <div class="contenu-fin">
        <header class="entete-fin">
          <div>
            <p class="sur-titre">Fin de l’audience</p>
            <h2 id="titre-fin" tabindex="-1" autofocus>Les deux camps ont plaidé. Et maintenant ?</h2>
          </div>
          <ol class="etapes-verdict" aria-label="Progression">
            <li class="fait"><span aria-hidden="true">✓</span> Audience</li>
            <li class="en-cours" aria-current="step"><span aria-hidden="true">2</span> Votez</li>
            <li><span aria-hidden="true">3</span> Verdict</li>
          </ol>
          <button class="fermer-verdict" type="button" aria-label="Revenir à l’audience" (click)="fenetreFin.close()">×</button>
        </header>
        <div class="portes-fin">
          <span class="ou-fin" aria-hidden="true">ou</span>
          <button type="button" class="porte-fin porte-fin--verdict" (click)="passerAuVerdict(fenetreFin, fenetreVerdict)">
            <span class="pastille-fin">Étape suivante</span>
            <span class="illustration-fin" aria-hidden="true"><img src="assets/tribunal-2/juge.png" alt=""></span>
            <span class="titre-porte">Passer au verdict</span>
            <span class="texte-porte">Départagez la Défense et le Procureur, chiffres clés à l’appui.</span>
            <span class="action-porte">Passer au verdict
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14m-6-6 6 6-6 6"/></svg></span>
          </button>
          <button type="button" class="porte-fin" (click)="poserQuestions(fenetreFin)">
            <span class="illustration-fin" aria-hidden="true"><img src="assets/greffier-transparent.png" alt=""></span>
            <span class="titre-porte">Poser plus de questions</span>
            <span class="texte-porte">Retournez au greffier : il garde le fil et le résumé de l’audience.</span>
            <span class="action-porte">Retour au greffier
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14m-6-6 6 6-6 6"/></svg></span>
          </button>
        </div>
      </div>
    </dialog>
    @if (annonceTerminee()) {
      <section class="decision-finale" aria-labelledby="titre-decision-finale">
        <h2 id="titre-decision-finale">Rapport comparatif</h2>
        @if (secondesAvantRapport() > 0) {
          <p class="attente-rapport" role="status">
            Ouverture dans {{ secondesAvantRapport() }} s
            <span class="points-rapport" aria-hidden="true"><i></i><i></i><i></i></span>
          </p>
        } @else {
          <button type="button" class="voir-comparaison"
            (click)="continuerComparaison.emit()">Ouvrir le rapport comparatif →</button>
        }
      </section>
    }
    <dialog #fenetreVerdict class="fenetre-verdict" aria-labelledby="titre-verdict" (close)="verdictOuvert.set(false)">
      <div class="contenu-verdict">
        <header class="entete-verdict">
          <div>
            <p class="sur-titre">Délibéré · étape finale</p>
            <h2 id="titre-verdict" tabindex="-1" autofocus>Qui a gagné le débat ? Votez.</h2>
          </div>
          <ol class="etapes-verdict" aria-label="Progression">
            <li class="fait"><span aria-hidden="true">✓</span> Audience</li>
            <li class="en-cours" aria-current="step"><span aria-hidden="true">2</span> Votez</li>
            <li><span aria-hidden="true">3</span> Verdict</li>
          </ol>
          <button class="fermer-verdict" type="button" aria-label="Revenir à l’audience" (click)="fenetreVerdict.close()">×</button>
        </header>
        <div class="corps-verdict">
          <div class="duel" role="radiogroup" aria-labelledby="titre-verdict">
            @for (camp of plaidoiries(); track camp.role; let i = $index) {
              <article class="camp" [attr.data-camp]="camp.role" [class.choisie]="vote() === camp.role"
                (click)="choisirCamp(camp.role, $any($event.currentTarget))">
                <input type="radio" name="vote-audience" [id]="'vote-' + camp.role" [value]="camp.role"
                  [checked]="vote() === camp.role" [disabled]="!camp.arguments.length"
                  [attr.aria-describedby]="'arguments-' + camp.role" (change)="vote.set(camp.role)">
                @if (vote() === camp.role) {
                  <span class="coche-camp" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg></span>
                }
                <div class="bande-camp">
                  <img [src]="camp.image + '.png'" alt="">
                  <div class="identite-camp">
                    <span class="lettre-camp" aria-hidden="true">{{ i === 0 ? 'A' : 'B' }}</span>
                    <h3>{{ camp.cote }}</h3>
                    <span class="avocat-camp">{{ camp.nom }}</span>
                    <span class="position-camp">{{ camp.role === 'avocat_defense' ? 'Pour la demande' : 'Contre la demande' }}</span>
                  </div>
                </div>
                @if (camp.chiffre; as c) {
                  <p class="chiffre-camp"><strong>{{ c.valeur }}</strong><span>{{ c.texte }}</span></p>
                }
                @if (camp.arguments.length) {
                  <ul class="arguments-camp" [id]="'arguments-' + camp.role">
                    @for (argument of camp.arguments; track $index) { <li>{{ argument }}</li> }
                  </ul>
                } @else {
                  <p class="arguments-camp" [id]="'arguments-' + camp.role">Plaidoirie indisponible.</p>
                }
                <label class="voter-camp" [for]="'vote-' + camp.role">
                  @if (vote() === camp.role) {
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>
                    Vous votez pour {{ camp.role === 'avocat_defense' ? 'la Défense' : 'le Procureur' }}
                  } @else {
                    Voter pour {{ camp.role === 'avocat_defense' ? 'la Défense' : 'le Procureur' }}
                  }
                </label>
              </article>
            }
          </div>
          <aside class="rail-rapport" aria-labelledby="titre-rail">
            <h3 id="titre-rail">Rapport d’analyse</h3>
            @if (chiffres(); as c) {
              <dl class="tuiles-rail">
                <div [class.alerte]="c.depasse"><dt>Pire baisse</dt><dd><strong>{{ pct(c.apres.pireBaisse) }}</strong><small>avant : {{ pct(c.avant.pireBaisse) }}</small></dd></div>
                <div><dt>Perte au pire</dt><dd><strong>{{ dollars(c.apres.pireBaisse * (proces()?.demande?.capital ?? 0)) }}</strong></dd></div>
                <div [class.alerte]="c.apres.partDuRisque > 0.25"><dt>Part du risque</dt><dd><strong>{{ pct(c.apres.partDuRisque, 0) }}</strong></dd></div>
                <div><dt>Mauvaise année</dt><dd><strong>{{ pct(c.apres.defavorable12Mois) }}</strong><small>avant : {{ pct(c.avant.defavorable12Mois) }}</small></dd></div>
              </dl>
            }
            <p class="scelle-rail">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 11V8a5 5 0 0 1 10 0v3M5 11h14v10H5zM12 15v2"/></svg>
              La décision du tribunal est révélée après votre vote, pour ne pas vous influencer.
            </p>
            <button type="button" class="rapport-complet" (click)="ouvrirRapport()">Ouvrir le rapport complet</button>
          </aside>
        </div>
        <footer class="pied-vote">
          <p role="status">
            @if (vote(); as v) {
              Votre choix : <strong>{{ v === 'avocat_defense' ? 'la Défense (A)' : 'le Procureur (B)' }}</strong>. Vous pouvez encore changer.
            } @else {
              Choisissez le camp qui vous a convaincu.
            }
          </p>
          <button type="button" class="rendre-verdict" [disabled]="!vote()"
            (click)="rendreVerdict(fenetreVerdict)">Rendre mon verdict →</button>
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
            [pendantLeVote]="verdictOuvert()"
            [audienceTerminee]="audienceTerminee() || !!verdictRendu() || verdictOuvert() || annonceTerminee()"
            [portefeuille]="portefeuille()"
            [masquerDecision]="!verdictRendu()" />
        }
        </div>
      </div>
      @if (rapportOuvert() && proces()) {
        <aside class="outils-rapport" aria-label="Emporter le rapport">
          <button type="button" class="outil-rapport outil-principal"
            [title]="chargementPdf() ? 'Génération du rapport en cours…' : 'Télécharger le rapport en PDF'"
            (click)="telecharger.emit(verdictRendu())"
            [disabled]="chargementPdf()"
            [class.en-chargement]="chargementPdf()">
            @if (chargementPdf()) {
              <svg class="icone-spin" viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2.5" stroke-dasharray="28 28"/>
              </svg>
              <span>Génération…</span>
            } @else if (succesPdf()) {
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>
              <span>Prêt !</span>
            } @else {
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v11m0 0-4.5-4.5M12 15l4.5-4.5M5 19h14"/></svg>
              <span>PDF</span>
            }
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
  readonly reprendreVote = input(false);
  readonly voteReprise = input<Camp | null>(null);
  /** Indicateur de génération du PDF en cours. */
  readonly chargementPdf = input(false);
  /** Indicateur de succès après téléchargement du PDF. */
  readonly succesPdf = input(false);
  /** Demande de PDF depuis le rapport, avec le camp retenu par l'investisseur. */
  readonly telecharger = output<'avocat_defense' | 'procureur' | null>();
  /** « Poser plus de questions » : retour au greffier. */
  readonly autreQuestion = output<void>();
  /** Le camp retenu, pour que le greffier puisse résumer l'audience au retour. */
  readonly voteRendu = output<Camp>();
  /** « Revenir voter » depuis le greffier : l'audience est déjà entendue, on ouvre le délibéré. */
  readonly delibere = input(false);
  private delibereOuvert = false;
  readonly continuerComparaison = output<void>();
  readonly secondesAvantRapport = signal(0);
  readonly index = linkedSignal({ source: this.tours, computation: () => 0 });
  readonly tour = computed<TourDiscussion | undefined>(() => this.annonceVerdict() ?? this.tours()[this.index()]);
  readonly preparation = computed(() => this.enCours() && !this.tour());
  readonly annoncesScene = computed(() => {
    const tour = this.tour();
    if (!tour) return [];
    if (tour.role === 'greffier' && (tour.statut === 'alerte' || tour.non_verifies?.length)) {
      return [{ tour, titre: 'Objection !' }];
    }
    return tour.role === 'temoin' ? [{ tour, titre: 'Témoin à la barre !' }] : [];
  });
  readonly dureeAnnonceMs = DUREE_ANNONCE_MS;
  private readonly annonceTermineePour = linkedSignal({
    source: this.tour,
    computation: (): TourDiscussion | undefined => undefined,
  });
  readonly annonceActive = computed(() => {
    const annonce = this.annoncesScene()[0];
    return !!annonce && this.annonceTermineePour() !== annonce.tour;
  });
  readonly mots = computed(() => motsDe(this.tour()?.texte ?? ''));
  readonly motsEnGras = computed(() => {
    const mots = this.mots().map((mot) => mot.toLocaleLowerCase('fr').normalize('NFC')
      .replace(/^[^\p{L}]+|[^\p{L}]+$/gu, '').replace(/‑/gu, '-'));
    const emphase = new Set<number>();
    for (const index of mots.keys()) {
      for (const expression of EXPRESSIONS_A_SOULIGNER) {
        if (expression.every((mot, offset) => mot === mots[index + offset])) {
          for (const offset of expression.keys()) emphase.add(index + offset);
        }
      }
    }
    return emphase;
  });
  readonly motActif = linkedSignal({ source: this.tour, computation: () => 0 });
  readonly texteIntegral = linkedSignal({ source: this.tour, computation: () => false });
  private readonly api = inject(ApiService);
  readonly analogieEnCours = signal(false);
  readonly analogieAffichee = signal(false);
  readonly cacheAnalogies = signal<Map<number, ReponseAnalogie>>(new Map());
  readonly analogieCourante = computed(() => {
    const t = this.tour();
    return t ? this.cacheAnalogies().get(t.ordre) : undefined;
  });
  readonly motsAnalogie = computed(() => motsDe(this.analogieCourante()?.analogie ?? ''));
  readonly motAnalogieActif = linkedSignal({ source: this.analogieCourante, computation: () => 0 });
  readonly analogieFinieDeLire = computed(() => {
    if (!this.analogieAffichee()) return true;
    if (this.analogieEnCours()) return false;
    const rep = this.analogieCourante();
    if (!rep) return false;
    return this.motAnalogieActif() >= this.motsAnalogie().length;
  });
  readonly repliqueDevoilee = computed(() => {
    const tourDevoile = this.texteIntegral() || this.motActif() >= this.mots().length;
    if (!this.analogieAffichee()) return tourDevoile;
    return tourDevoile && this.analogieFinieDeLire();
  });
  readonly lectureAuto = signal(true);
  readonly sonActive = signal(true);
  readonly sonBloque = signal(false);
  readonly boutonVerdict = viewChild<TemplateRef<unknown>>('boutonVerdict');
  readonly verdictOuvert = signal(false);
  readonly rapportOuvert = signal(false);
  readonly finOuverte = signal(false);
  /** Le coup de marteau du bouton « Terminé », juste avant d'ouvrir le choix de fin d'audience. */
  readonly impactVerdict = signal(false);
  private minuterieVerdict?: ReturnType<typeof setTimeout>;
  readonly chiffres = computed(() => chiffresCles(this.proces()));
  readonly pct = pct;
  readonly dollars = dollars;
  readonly vote = linkedSignal<readonly TourDiscussion[], Camp | null>({ source: this.tours, computation: () => null });
  readonly verdictRendu = linkedSignal<readonly TourDiscussion[], Camp | null>({
    source: this.tours, computation: () => null,
  });
  private readonly repriseAppliquee = signal(false);
  readonly lectureActive = computed(() =>
    !this.annonceActive() && !this.verdictOuvert() && !this.finOuverte() && !this.rapportOuvert()
    && !this.analogieAffichee()
    && this.lectureAuto()
    && this.motActif() < this.mots().length);
  readonly audienceTerminee = computed(() =>
    !this.verdictRendu() && this.index() === this.tours().length - 1 && this.repliqueDevoilee());
  readonly annonceTerminee = computed(() => !!this.verdictRendu() && this.motActif() >= this.mots().length);
  readonly libelleLecture = computed(() => {
    if (this.annonceTerminee()) return 'Rejouer l’annonce';
    if (this.audienceTerminee()) return 'Rejouer l’audience';
    return this.lectureAuto() ? 'Mettre la lecture en pause' : 'Reprendre la lecture';
  });
  readonly personnages = PERSONNAGES;
  readonly plaidoiries = computed(() => PERSONNAGES.filter((p) => p.role !== 'juge').map((p) => {
    const texte = this.tours().find((tour) => tour.role === p.role)?.texte ?? '';
    const c = this.chiffres();
    const t = this.proces()?.demande.ticker ?? 'le titre';
    const budget = this.proces()?.budgetPerte ?? 0;
    // Le chiffre qui sert le mieux chaque camp : la pire baisse face au budget pour la défense,
    // la concentration du risque pour l'accusation.
    const chiffre = !c ? null : p.role === 'avocat_defense'
      ? { valeur: pct(c.apres.pireBaisse), texte: `pire baisse avec ${t}, pour un budget déclaré de ${pct(budget, 0)}` }
      : { valeur: pct(c.apres.partDuRisque, 0), texte: `du risque porté par ${t}, pour ${pct(this.proces()?.demande.taille ?? 0, 0)} du portefeuille` };
    return { ...p, arguments: texte ? argumentsDe(texte, 3) : [], chiffre };
  }));
  readonly campRetenu = computed(() => this.plaidoiries().find((camp) => camp.role === this.verdictRendu()));
  private readonly annonceVerdict = computed<TourDiscussion | undefined>(() => {
    const camp = this.campRetenu();
    if (!camp) return;
    const cote = camp.role === 'avocat_defense' ? 'la défense' : 'l’accusation';
    const verdict = this.proces()?.decision.verdict;
    return {
      ordre: this.tours().length + 1,
      etape: 'ANNONCE_VERDICT',
      acteur: 'Le juge',
      role: 'juge',
      avatar: '👨‍⚖️',
      titre: 'Votre verdict',
      texte: `Vous avez tranché en faveur de ${cote}, représentée par ${camp.nom}. `
        + (verdict ? `Le verdict du tribunal est « ${verdict} ». ` : '')
        + 'L’audience est levée.',
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
  private readonly blobsParPersonnage = computed(() => {
    const disponibles: number[] = [];
    const portraits = new Map<string, number>();
    for (const tour of this.tours()) {
      if (PERSONNAGES.some((personnage) => personnage.role === tour.role)) continue;
      const cle = clePortrait(tour);
      if (portraits.has(cle)) continue;
      if (!disponibles.length) disponibles.push(...BLOBS);
      const index = Math.floor(Math.random() * disponibles.length);
      const [blob] = disponibles.splice(index, 1);
      portraits.set(cle, blob);
    }
    return portraits;
  });
  readonly blobActif = computed(() => {
    const tour = this.tour();
    return tour ? this.blobsParPersonnage().get(clePortrait(tour)) : undefined;
  });
  readonly portrait = computed(() => {
    const personnage = PERSONNAGES.find((p) => p.role === this.tour()?.role);
    if (personnage) return personnage.image + '.png';
    const blob = this.blobActif();
    return blob ? `assets/tribunal-2/blob-${blob}.png` : null;
  });
  private readonly replique = viewChild<ElementRef<HTMLElement>>('replique');
  private readonly voixAudience = linkedSignal({ source: this.tours, computation: choisirVoixAudience });
  private readonly sonAudience = inject(SonAudienceService);
  private readonly lecteur = this.sonAudience.lecteur;
  private dernierTourSon?: TourDiscussion;
  private readonly ancrageSon = viewChild<ElementRef<HTMLElement>>('ancrageSon');
  private readonly fenetreRapport = viewChild<ElementRef<HTMLDialogElement>>('fenetreRapport');
  private readonly fenetreVerdict = viewChild<ElementRef<HTMLDialogElement>>('fenetreVerdict');

  constructor() {
    const page = inject(ElementRef<HTMLElement>).nativeElement.closest('rdc-tribunal');
    inject(DestroyRef).onDestroy(() => {
      clearTimeout(this.minuterieVerdict);
      this.sonAudience.arreterAmbianceSalle();
    });
    afterNextRender(() => this.ancrageSon()?.nativeElement.append(this.lecteur));
    effect((nettoyer) => {
      if (!this.annonceTerminee() || this.reprendreVote()) return;
      let secondes = 3;
      this.secondesAvantRapport.set(secondes);
      const minuterie = setInterval(() => {
        this.secondesAvantRapport.set(--secondes);
        if (secondes > 0) return;
        clearInterval(minuterie);
        this.continuerComparaison.emit();
      }, 1000);
      nettoyer(() => {
        clearInterval(minuterie);
        this.secondesAvantRapport.set(0);
      });
    });
    // Retour depuis le greffier pour voter : dernière réplique affichée en entier, délibéré ouvert.
    afterRenderEffect(() => {
      const fenetre = this.fenetreVerdict()?.nativeElement;
      if (!this.delibere() || this.delibereOuvert || !this.tours().length || !fenetre) return;
      this.delibereOuvert = true;
      this.lectureAuto.set(false);
      this.index.set(this.tours().length - 1);
      this.texteIntegral.set(true);
      this.motActif.set(this.mots().length);
      this.verdictOuvert.set(true);
      fenetre.showModal();
    });
    effect(() => {
      if (!this.reprendreVote() || this.repriseAppliquee()) return;
      const camp = this.voteReprise();
      if (!camp || !this.tours().length) return;
      this.vote.set(camp);
      this.verdictRendu.set(camp);
      this.lectureAuto.set(false);
      this.texteIntegral.set(true);
      this.motActif.set(this.mots().length);
      this.repriseAppliquee.set(true);
    });
    afterRenderEffect(() => {
      if (this.verdictRendu()) this.replique()?.nativeElement.focus({ preventScroll: true });
    });
    effect(() => {
      const tour = this.tour();
      if (!tour || this.annonceActive()) return;
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
          if (this.analogieAffichee() && !this.analogieFinieDeLire()) {
            this.motActif.set(mots.length);
            return;
          }
          this.afficherTour(this.index() + 1);
        } else {
          this.motActif.set(indexMot + 1);
        }
      }, MS_PAR_MOT + pause);
      nettoyer(() => clearTimeout(minuterie));
    });

    // Lecture progressive de l'analogie : elle défile mot par mot et empêche le discours de changer tant qu'elle n'est pas finie de lire
    effect((nettoyer) => {
      if (!this.analogieAffichee() || this.analogieEnCours()) return;
      const rep = this.analogieCourante();
      if (!rep) return;
      const mots = this.motsAnalogie();
      const indexMot = this.motAnalogieActif();
      if (indexMot >= mots.length) {
        if (this.lectureAuto() && !this.verdictRendu() && this.index() < this.tours().length - 1) {
          const minuterieFin = setTimeout(() => {
            if (this.analogieAffichee() && this.analogieFinieDeLire()) {
              this.fermerAnalogie();
              this.afficherTour(this.index() + 1);
            }
          }, 3500);
          nettoyer(() => clearTimeout(minuterieFin));
        }
        return;
      }
      const mot = mots[indexMot];
      const pause = FIN_DE_PHRASE.test(mot) ? 140 : PAUSE_COURTE.test(mot) ? 70 : 0;
      const minuterie = setTimeout(() => {
        if (!this.analogieAffichee() || this.analogieCourante() !== rep || this.motAnalogieActif() !== indexMot) return;
        this.motAnalogieActif.set(indexMot + 1);
      }, MS_PAR_MOT_ANALOGIE + pause);
      nettoyer(() => clearTimeout(minuterie));
    });

    effect((nettoyer) => {
      const preparation = this.preparation();
      if (!preparation) this.sonAudience.arreterAmbianceSalle();
      if (!this.sonActive() || this.sonBloque()) return;
      if (preparation) {
        this.jouerAmbianceSalle();
      } else if (this.annonceActive()) {
        if (this.verdictOuvert() || this.rapportOuvert()) return;
        this.jouerImpactAnnonce();
      } else {
        if (!this.lectureActive()) return;
        this.jouerVoix();
      }
      nettoyer(() => this.lecteur.pause());
    });

    afterRenderEffect((nettoyer) => {
      const annonce = this.annoncesScene()[0];
      if (!annonce) return;
      const secousse = window.matchMedia('(prefers-reduced-motion: reduce)').matches
        ? undefined
        : page?.animate([
          { translate: '0 0' },
          { translate: '-6px 2px' },
          { translate: '5px -2px' },
          { translate: '-3px 1px' },
          { translate: '2px -1px' },
          { translate: '0 0' },
        ], { duration: 320 });
      const minuterie = setTimeout(() => this.annonceTermineePour.set(annonce.tour), DUREE_ANNONCE_MS);
      nettoyer(() => {
        clearTimeout(minuterie);
        secousse?.cancel();
      });
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
    if (this.annonceActive()) return;
    if (this.analogieAffichee() && !this.analogieFinieDeLire()) {
      this.motAnalogieActif.set(this.motsAnalogie().length);
      return;
    }
    if (!this.repliqueDevoilee()) {
      this.motActif.set(this.mots().length);
      return;
    }
    if (this.analogieAffichee()) {
      this.fermerAnalogie();
    }
    this.afficherTour(this.index() + 1);
  }

  devoilerAnalogieComplete(): void {
    if (!this.analogieFinieDeLire()) {
      this.motAnalogieActif.set(this.motsAnalogie().length);
    }
  }

  continuerApresAnalogie(): void {
    this.fermerAnalogie();
    if (this.index() < this.tours().length - 1) {
      this.afficherTour(this.index() + 1);
    }
  }

  afficherTour(index: number): void {
    if (index < 0 || index >= this.tours().length) return;
    const panneau = this.replique()?.nativeElement;
    if (panneau) panneau.scrollTop = 0;
    this.index.set(index);
    this.motActif.set(0);
    this.texteIntegral.set(!this.lectureAuto());
    this.dernierTourSon = undefined;
    this.analogieAffichee.set(false);
    this.motAnalogieActif.set(0);
  }

  basculerAnalogie(): void {
    const tour = this.tour();
    if (!tour) return;
    if (this.analogieAffichee() && !!this.analogieCourante()) {
      this.analogieAffichee.set(false);
      return;
    }
    this.motActif.set(this.mots().length);
    const existant = this.cacheAnalogies().get(tour.ordre);
    if (existant) {
      this.motAnalogieActif.set(0);
      this.analogieAffichee.set(true);
      return;
    }
    this.motAnalogieActif.set(0);
    this.analogieEnCours.set(true);
    this.analogieAffichee.set(true);
    this.api.demanderAnalogie({
      texte: tour.texte,
      acteur: tour.acteur,
      role: tour.role,
      mode: 'bedrock',
    }).subscribe({
      next: (rep) => {
        this.cacheAnalogies.update((map) => new Map(map).set(tour.ordre, rep));
        this.motAnalogieActif.set(0);
        this.analogieEnCours.set(false);
      },
      error: () => {
        const fallback: ReponseAnalogie = {
          analogie: "Voyez cela comme une traversée en mer : par vent fort, mieux vaut vérifier que les gilets et amarres sont solides avant d'accélérer.",
          titre: "L'analogie du juré",
          source: 'secours',
        };
        this.cacheAnalogies.update((map) => new Map(map).set(tour.ordre, fallback));
        this.motAnalogieActif.set(0);
        this.analogieEnCours.set(false);
      },
    });
  }

  fermerAnalogie(): void {
    this.analogieAffichee.set(false);
  }

  /** « Terminé » : coup de marteau, puis le choix entre passer au verdict et poser plus de questions. */
  ouvrirFin(fenetre: HTMLDialogElement): void {
    if (fenetre.open || this.finOuverte()) return;
    this.finOuverte.set(true);
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


  passerAuVerdict(fin: HTMLDialogElement, verdict: HTMLDialogElement): void {
    fin.close();
    this.verdictOuvert.set(true);
    verdict.showModal();
  }

  /** Un clic n'importe où sur la carte choisit le camp et y met le focus (flèches ↑ ↓ ensuite). */
  choisirCamp(camp: Camp, carte: HTMLElement): void {
    const radio = carte.querySelector('input');
    if (!radio || radio.disabled) return;
    this.vote.set(camp);
    radio.focus({ preventScroll: true });
  }

  poserQuestions(fin: HTMLDialogElement): void {
    fin.close();
    this.autreQuestion.emit();
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
    this.voteRendu.emit(choix);
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
    if (this.preparation()) this.jouerAmbianceSalle();
    else if (this.lectureActive()) this.jouerVoix();
  }

  private jouerAmbianceSalle(): void {
    this.surveillerLecture(this.sonAudience.jouerAmbianceSalle());
  }

  private jouerImpactAnnonce(): void {
    const lecteur = this.lecteur;
    lecteur.src = 'assets/tribunal-2/voix/impact-annonce.wav';
    lecteur.loop = false;
    lecteur.volume = 0.75;
    lecteur.playbackRate = 1;
    this.lancerSon();
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
    this.lancerSon();
  }

  private lancerSon(): void {
    this.surveillerLecture(this.lecteur.play());
  }

  private surveillerLecture(lecture: Promise<void>): void {
    void lecture.catch((erreur: DOMException) => {
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
