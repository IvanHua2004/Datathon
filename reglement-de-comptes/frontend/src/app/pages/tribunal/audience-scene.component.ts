import { Component, DestroyRef, ElementRef, TemplateRef, afterNextRender, afterRenderEffect, computed, effect, inject, input, linkedSignal, output, signal, viewChild } from '@angular/core';
import { DUREE_EFFET_PIECES, PiecesMonnaieComponent } from '../../components/pieces-monnaie/pieces-monnaie.component';
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
type Camp = 'avocat_defense' | 'procureur';

/** Un duel A contre B joué dans la même salle : Me Vigor défend A, Me Austère défend B. */
export interface ConfigDuel {
  camps: Record<Camp, { ticker: string; nomTitre: string }>;
  /** La décision du tribunal, révélée seulement après le vote. */
  annonce: string;
  /** Les chiffres clés côte à côte dans le rail du vote. */
  tuiles: readonly { libelle: string; a: string; b: string; alerteA: boolean; alerteB: boolean }[];
}

function motsDe(texte: string): string[] {
  return texte.match(/\S+\s*/gu) ?? [];
}

const PERSONNAGES = [
  { role: 'avocat_defense', image: 'assets/tribunal-2/defense', emplacement: 'gauche', nom: 'Me Vigor', cote: 'La Défense' },
  { role: 'juge', image: 'assets/tribunal-2/juge', emplacement: 'centre' },
  { role: 'procureur', image: 'assets/tribunal-2/procureur', emplacement: 'droite', nom: 'Me Austère', cote: 'Le Procureur' },
] as const;

const BLOBS = [1, 3, 4, 5, 6, 7, 8, 9];
const TRAJECTOIRES_TOMATE = ['horizontale', 'montante', 'descendante', 'cloche'] as const;

function clePortrait(tour: TourDiscussion): string {
  return tour.role === 'temoin' ? tour.temoin || tour.acteur : tour.role + ':' + tour.acteur;
}

@Component({
  selector: 'rdc-audience-scene',
  imports: [RapportAudienceComponent, PiecesMonnaieComponent],
  templateUrl: './audience-scene.component.html',
  styleUrl: './audience-scene.component.scss',
})
export class AudienceSceneComponent {
  readonly tours = input<readonly TourDiscussion[]>([]);
  readonly pieces = input<readonly Piece[]>([]);
  readonly enCours = input(false);
  /** Duel entre deux titres : mêmes personnages, autre question, autres libellés. */
  readonly duel = input<ConfigDuel | null>(null);
  /** Texte affiché pendant la préparation (le duel annonce ses deux procès). */
  readonly messageAttente = input<string | null>(null);
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
  readonly ouvertureRapport = signal(false);
  readonly imagesMarteau = [1, 2, 3, 4];
  readonly imageMarteau = signal<number | null>(null);
  private minuteriesMarteau: ReturnType<typeof setTimeout>[] = [];
  readonly index = linkedSignal({ source: this.tours, computation: () => 0 });
  readonly tour = computed<TourDiscussion | undefined>(() => this.annonceVerdict() ?? this.tours()[this.index()]);
  readonly preparation = computed(() => this.enCours() && !this.tour());
  readonly tomate = signal<{
    depuisDroite: boolean;
    trajectoire: typeof TRAJECTOIRES_TOMATE[number];
  } | null>(null);
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
    const motsBruts = this.mots();
    const mots = motsBruts.map((mot) => mot.toLocaleLowerCase('fr').normalize('NFC')
      .replace(/^[^\p{L}]+|[^\p{L}]+$/gu, '').replace(/‑/gu, '-'));
    const emphase = new Set<number>();
    for (const index of mots.keys()) {
      for (const expression of EXPRESSIONS_A_SOULIGNER) {
        if (expression.every((mot, offset) => mot === mots[index + offset])) {
          for (const offset of expression.keys()) emphase.add(index + offset);
        }
      }
    }
    if (this.tour()?.etape === 'ANNONCE_VERDICT') {
      const debut = motsBruts.findIndex((mot) => mot.trim() === '«');
      const fin = motsBruts.findIndex((mot, index) => index > debut && mot.trim().startsWith('»'));
      if (debut >= 0 && fin > debut) {
        for (let index = debut + 1; index < fin; index++) emphase.add(index);
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
    this.imageMarteau() === null
    && !this.annonceActive() && !this.verdictOuvert() && !this.finOuverte() && !this.rapportOuvert()
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
  readonly personnages = computed(() => {
    const duel = this.duel();
    return PERSONNAGES.map((p) => p.role === 'juge' || !duel ? p
      : { ...p, cote: `Avocat de ${duel.camps[p.role].ticker}` });
  });
  /** « la Défense » / « le Procureur », ou le titre défendu pendant un duel. */
  libelleCamp(role: Camp): string {
    const duel = this.duel();
    if (duel) return duel.camps[role].ticker;
    return role === 'avocat_defense' ? 'la Défense' : 'le Procureur';
  }
  readonly plaidoiries = computed(() => this.personnages().filter((p) => p.role !== 'juge').map((p) => {
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
    const duel = this.duel();
    const cote = camp.role === 'avocat_defense' ? 'la défense' : 'l’accusation';
    const verdict = this.proces()?.decision.verdict;
    const texte = duel
      ? `Vous avez tranché en faveur de ${duel.camps[camp.role].ticker}, défendu par ${camp.nom}. `
        + `${duel.annonce} L’audience est levée.`
      : `Vous avez tranché en faveur de ${cote}, représentée par ${camp.nom}. `
        + (verdict ? `Le verdict du tribunal est « ${verdict} ». ` : '')
        + 'L’audience est levée.';
    return {
      ordre: this.tours().length + 1,
      etape: 'ANNONCE_VERDICT',
      acteur: 'Le juge',
      role: 'juge',
      avatar: '👨‍⚖️',
      titre: 'Votre verdict',
      texte,
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
  readonly portraitEnErreur = linkedSignal({ source: this.portrait, computation: () => false });
  readonly portraitVisible = computed(() => this.portraitEnErreur() ? null : this.portrait());
  private readonly replique = viewChild<ElementRef<HTMLElement>>('replique');
  private readonly voixAudience = linkedSignal({ source: this.tours, computation: choisirVoixAudience });
  private readonly sonAudience = inject(SonAudienceService);
  private readonly lecteur = this.sonAudience.lecteur;
  private dernierTourSon?: TourDiscussion;
  private readonly ancrageSon = viewChild<ElementRef<HTMLElement>>('ancrageSon');
  private readonly fenetreRapport = viewChild<ElementRef<HTMLDialogElement>>('fenetreRapport');
  private readonly fenetreVerdict = viewChild<ElementRef<HTMLDialogElement>>('fenetreVerdict');

  constructor() {
    const page = inject(ElementRef<HTMLElement>).nativeElement.closest('rdc-tribunal, rdc-duel');
    inject(DestroyRef).onDestroy(() => {
      clearTimeout(this.minuterieVerdict);
      for (const minuterie of this.minuteriesMarteau) clearTimeout(minuterie);
      if (this.imageMarteau() !== null) this.lecteur.pause();
    });
    afterNextRender(() => this.ancrageSon()?.nativeElement.append(this.lecteur));
    effect((nettoyer) => {
      if (!this.annonceTerminee() || this.reprendreVote()) return;
      if (this.duel()) {
        // Duel : pas de tableau de bord à ouvrir, la page du duel fait défiler jusqu'à la décision.
        const fin = setTimeout(() => this.continuerComparaison.emit(), 1500);
        nettoyer(() => clearTimeout(fin));
        return;
      }
      let minuterie = setTimeout(() => {
        this.ouvertureRapport.set(true);
        minuterie = setTimeout(() => {
          this.continuerComparaison.emit();
          this.ouvertureRapport.set(false);
        }, 4000);
      }, 2000);
      nettoyer(() => {
        clearTimeout(minuterie);
        this.ouvertureRapport.set(false);
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
    effect((nettoyer) => {
      if (!this.tours().length) return;
      let minuterie: ReturnType<typeof setTimeout>;
      const lancer = () => {
        if (this.verdictRendu() || this.audienceTerminee()) return;
        if (document.hidden || this.annonceActive() || this.finOuverte() || this.verdictOuvert() || this.rapportOuvert()) {
          minuterie = setTimeout(lancer, 800);
          return;
        }
        this.tomate.set({
          depuisDroite: Math.random() < 0.5,
          trajectoire: TRAJECTOIRES_TOMATE[Math.floor(Math.random() * TRAJECTOIRES_TOMATE.length)],
        });
        minuterie = setTimeout(() => {
          this.tomate.set(null);
          minuterie = setTimeout(lancer, 2400 + Math.random() * 3000);
        }, 1600);
      };
      minuterie = setTimeout(lancer, 2000 + Math.random() * 2000);
      nettoyer(() => {
        clearTimeout(minuterie);
        this.tomate.set(null);
      });
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
      if (this.preparation()) {
        void this.sonAudience.jouerAmbianceSalle().catch(() => {
          // Le navigateur peut bloquer le son lors d’une ouverture directe.
        });
        nettoyer(() => this.sonAudience.arreterAmbianceSalle());
        return;
      }
      if (!this.sonActive() || this.sonBloque()) return;
      if (this.annonceActive()) {
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

  ouvrirFin(fenetre: HTMLDialogElement): void {
    if (fenetre.open || this.finOuverte()) return;
    this.finOuverte.set(true);
    this.impactVerdict.set(true);
    this.minuterieVerdict = setTimeout(() => {
      this.impactVerdict.set(false);
      fenetre.showModal();
    }, DUREE_EFFET_PIECES);
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
    if (!choix || this.imageMarteau() !== null) return;
    const mouvementReduit = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.imageMarteau.set(mouvementReduit ? 4 : 1);
    this.voteRendu.emit(choix);
    fenetre.close();
    this.verdictOuvert.set(false);

    const frapper = () => {
      this.imageMarteau.set(4);
      if (!this.sonActive()) return;
      this.sonBloque.set(false);
      const lecteur = this.lecteur;
      lecteur.src = 'assets/tribunal-2/voix/coup-marteau.wav';
      lecteur.loop = false;
      lecteur.volume = 1;
      lecteur.playbackRate = 1;
      this.lancerSon();
    };
    if (mouvementReduit) {
      frapper();
    } else {
      this.minuteriesMarteau.push(
        setTimeout(() => this.imageMarteau.set(2), 125),
        setTimeout(() => this.imageMarteau.set(3), 255),
        setTimeout(frapper, 400),
      );
    }
    this.minuteriesMarteau.push(setTimeout(() => {
      this.minuteriesMarteau = [];
      this.verdictRendu.set(choix);
      this.lectureAuto.set(true);
      const panneau = this.replique()?.nativeElement;
      if (panneau) panneau.scrollTop = 0;
      this.imageMarteau.set(null);
    }, mouvementReduit ? 435 : 835));
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
