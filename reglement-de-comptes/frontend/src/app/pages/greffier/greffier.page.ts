import { HttpErrorResponse } from '@angular/common/http';
import {
  Component, ElementRef, WritableSignal, computed, effect, inject, input, signal, viewChild,
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { EnteteComponent } from '../../components/entete/entete.component';
import { AnalyseQuestion, ChoixDossier } from '../../models/question.model';
import { ApiService } from '../../services/api.service';
import { DicteeService } from '../../services/dictee.service';
import { ProcesService } from '../../services/proces.service';
import { SonAudienceService } from '../../services/son-audience.service';
import { Attente, completer } from '../../shared/autocompletion';
import { dollars, pct } from '../../shared/format';
import { AudienceSuspendue, Retour, cleConversation, cleRetour, ecrire, effacer, lire } from '../../shared/memoire';

interface Message {
  de: 'greffier' | 'archiviste' | 'moi';
  texte: string;
  ton?: 'ok' | 'refus' | 'question' | 'erreur' | 'info';
  analyse?: AnalyseQuestion;
  /** Retour du tribunal : la carte « Audience suspendue » et ses actions. */
  audience?: AudienceSuspendue;
  /** Questions toutes prêtes, à cliquer (l'archiviste sur le débat). */
  suggestions?: string[];
  /** Titres cochés quand l'archiviste fait choisir deux titres à comparer. */
  choisis?: WritableSignal<string[]>;
}

/** Forme sauvegardée d'un message (les signaux ne se sérialisent pas). */
type MessageSauve = Omit<Message, 'choisis'> & { choisis?: string[] };

interface Sauvegarde {
  messages: MessageSauve[];
  debutContexte: number;
  enAttente: { ticker: string | null; taille: number | null; attente: Attente };
}

/** Étape 2 : l'investisseur pose sa question au greffier, qui dit si le tribunal peut la juger. */
@Component({
  selector: 'rdc-greffier',
  imports: [RouterLink, EnteteComponent],
  templateUrl: './greffier.page.html',
  styleUrl: './greffier.page.css',
})
export class GreffierPage {
  private readonly api = inject(ApiService);
  readonly dictee = inject(DicteeService);
  /** Vrai tant que la phrase dictée n'est pas fixée (affichée en gris). */
  readonly dicteeProvisoire = signal(false);
  private readonly sonAudience = inject(SonAudienceService);
  private readonly router = inject(Router);
  readonly tribunal = inject(ProcesService);
  readonly pct = pct;
  readonly dollars = dollars;

  /** Lu dans l'URL : /question?profil=robert */
  readonly profil = input<string>('');

  readonly messages = signal<Message[]>([]);
  readonly saisie = signal('');
  readonly enCours = signal(false);
  readonly ouverte = signal(false);          // liste de suggestions visible
  readonly active = signal(-1);              // suggestion surlignée au clavier
  private readonly enAttente = signal<{ ticker: string | null; taille: number | null; attente: Attente }>(
    { ticker: null, taille: null, attente: null },
  );

  /** Les questions avant cet indice sont oubliées (bouton ✕ du contexte, « recommence »). */
  private readonly debutContexte = signal(0);

  /** Ce que le greffier a retenu : le titre (et la part) le plus récent de la conversation. */
  readonly contexte = computed(() => {
    const attente = this.enAttente();
    const moi = this.messages().filter((m) => m.de === 'moi').length;
    if (moi <= this.debutContexte()) return null;
    for (const m of [...this.messages()].reverse()) {
      const a = m.analyse;
      if (m.de === 'moi' || !a) continue;
      if (a.ticker && a.nomTitre) {
        return { titre: `${a.nomTitre} (${a.ticker})`, taille: a.taille ?? attente.taille };
      }
      if (a.fiches?.length === 2) {
        return { titre: `${a.fiches[0].ticker} et ${a.fiches[1].ticker}`, taille: null };
      }
    }
    return null;
  });

  private restaure = false;

  private readonly fil = viewChild<ElementRef<HTMLElement>>('fil');
  private readonly champ = viewChild<ElementRef<HTMLInputElement>>('champ');

  readonly persona = computed(() => this.tribunal.profils().find((p) => p.cle === this.profil()) ?? null);

  /**
   * Le titre suit le parcours : avant le tribunal, l'audience préliminaire ; au retour, la suite de
   * l'audience (verdict à rendre) ; après le vote, l'après-verdict.
   */
  readonly titre = computed(() => {
    const audience = [...this.messages()].reverse().find((m) => m.audience)?.audience;
    if (!audience) return 'Audience préliminaire';
    return audience.vote || this.tribunal.voteAudience() ? 'Après le verdict' : 'Suite de l’audience';
  });

  /** « de votre portefeuille », sauf si la note du persona ne décrit pas ses positions. */
  readonly dePortefeuille = computed(() =>
    this.persona()?.portefeuilleDeclare === false ? 'du portefeuille de référence' : 'de votre portefeuille');

  readonly suggestions = computed(() => {
    const p = this.persona();
    if (!p || this.enCours()) return [];
    return completer(this.saisie(), {
      actifs: this.tribunal.actifs(),
      attente: this.enAttente().attente,
      exemple: p.demandeExemple.ticker,
    });
  });

  readonly listeVisible = computed(() => this.ouverte() && this.suggestions().length > 0);

  constructor() {
    this.tribunal.chargerReferentiels();

    // Sans persona valide, retour au choix du persona.
    effect(() => {
      const profils = this.tribunal.profils();
      if (profils.length && !this.persona()) {
        this.router.navigate(['/personas']);
      }
    });

    // Le greffier ouvre l'audience dès que le persona est connu, ou reprend la conversation.
    effect(() => {
      const p = this.persona();
      if (!p || this.restaure) return;
      this.restaure = true;
      const sauve = lire<Sauvegarde>(cleConversation(p.cle));
      if (sauve?.messages?.length) {
        this.messages.set(sauve.messages.map((m) => ({
          ...m,
          choisis: m.choisis ? signal(m.choisis) : undefined,
        })));
        this.debutContexte.set(sauve.debutContexte ?? 0);
        this.enAttente.set(sauve.enAttente ?? { ticker: null, taille: null, attente: null });
      } else {
        this.accueillir(p.nom);
      }
      // Retour du tribunal ou du duel : le greffier résume ce qui a été jugé.
      const retour = lire<Retour>(cleRetour(p.cle));
      if (retour?.texte) {
        effacer(cleRetour(p.cle));
        if (retour.audience) {
          // La carte reprend l'audience : revenir voter, interroger l'archiviste, ou un autre débat.
          this.ajouter({ de: 'greffier', ton: 'info', texte: retour.texte, audience: retour.audience });
          // « Et avec 5 % ? » vise le même titre.
          this.enAttente.set({ ticker: retour.audience.ticker, taille: null, attente: null });
        } else {
          this.ajouter({ de: 'greffier', ton: 'info', texte: retour.texte });
          this.ajouter({ de: 'greffier', ton: 'question', texte: 'Une autre décision à soumettre au tribunal ?' });
        }
      }
      // Au retour d'audience, la carte doit rester visible : pas de focus (qui ouvrirait les suggestions).
      const carteAudience = !!retour?.audience;
      setTimeout(() => {
        if (!carteAudience) this.champ()?.nativeElement.focus();
        const fil = this.fil()?.nativeElement;
        fil?.scrollTo({ top: fil.scrollHeight });
      });
    });

    // Sauvegarde à chaque changement, pour survivre à un aller-retour vers le tribunal.
    effect(() => {
      const p = this.persona();
      const messages = this.messages();
      if (!p || !this.restaure) return;
      ecrire(cleConversation(p.cle), {
        messages: messages.map((m) => ({ ...m, choisis: m.choisis?.() })),
        debutContexte: this.debutContexte(),
        enAttente: this.enAttente(),
      } satisfies Sauvegarde);
    });
  }

  private accueillir(nom: string): void {
    this.messages.set([{
      de: 'greffier',
      ton: 'question',
      texte: `Bonjour ${nom}. Quelle décision voulez-vous soumettre au tribunal ? `
        + `Nommez un titre et la part ${this.dePortefeuille()}.`,
    }]);
  }

  /** ✕ sur l'étiquette « Contexte » : les questions précédentes ne comptent plus. */
  effacerContexte(): void {
    this.debutContexte.set(this.messages().filter((m) => m.de === 'moi').length);
    this.enAttente.set({ ticker: null, taille: null, attente: null });
    this.champ()?.nativeElement.focus();
  }

  nouvelleConversation(): void {
    const p = this.persona();
    if (!p) return;
    effacer(cleConversation(p.cle));
    this.debutContexte.set(0);
    this.enAttente.set({ ticker: null, taille: null, attente: null });
    this.saisie.set('');
    this.accueillir(p.nom);
    this.champ()?.nativeElement.focus();
  }

  // ----- Saisie et suggestions -----

  /** Micro : dicter la question au lieu de la taper. Rien n'est envoyé sans Entrée. */
  basculerDictee(): void {
    if (this.dictee.actif()) {
      this.dictee.arreter();
      return;
    }
    const debut = this.saisie().trim();
    this.ouverte.set(false);
    this.dictee.demarrer({
      texte: (texte, provisoire) => {
        this.saisie.set(debut ? `${debut} ${texte}` : texte);
        this.dicteeProvisoire.set(provisoire);
        this.ouverte.set(false);
      },
      fin: () => {
        this.dicteeProvisoire.set(false);
        const champ = this.champ()?.nativeElement;
        champ?.focus();
        champ?.setSelectionRange(champ.value.length, champ.value.length);
        this.ouverte.set(false);
      },
    });
  }

  taper(event: Event): void {
    this.saisie.set((event.target as HTMLInputElement).value);
    this.ouverte.set(true);
    this.active.set(-1);
  }

  clavier(event: KeyboardEvent): void {
    const liste = this.listeVisible() ? this.suggestions() : [];
    switch (event.key) {
      case 'ArrowDown':
        if (!liste.length) return;
        event.preventDefault();
        this.active.set((this.active() + 1) % liste.length);
        break;
      case 'ArrowUp':
        if (!liste.length) return;
        event.preventDefault();
        this.active.set(this.active() <= 0 ? liste.length - 1 : this.active() - 1);
        break;
      case 'Tab':
        if (!liste.length || event.shiftKey) return;
        event.preventDefault();
        this.accepter(liste[Math.max(this.active(), 0)]);
        break;
      case 'Enter':
        event.preventDefault();
        if (this.active() >= 0 && liste[this.active()]) {
          this.accepter(liste[this.active()]);
        } else {
          this.envoyer();
        }
        break;
      case 'Escape':
        this.ouverte.set(false);
        this.active.set(-1);
        break;
    }
  }

  accepter(suggestion: string): void {
    this.saisie.set(suggestion);
    this.active.set(-1);
    this.ouverte.set(true);
    const champ = this.champ()?.nativeElement;
    if (champ) {
      champ.value = suggestion;
      champ.focus();
      champ.setSelectionRange(suggestion.length, suggestion.length);
    }
  }

  /** Découpe une suggestion en « déjà tapé » + « complétion » pour mettre la suite en gras. */
  morceaux(suggestion: string): { tape: string; suite: string } {
    const tape = this.saisie();
    if (tape && suggestion.toLowerCase().startsWith(tape.toLowerCase())) {
      return { tape: suggestion.slice(0, tape.length), suite: suggestion.slice(tape.length) };
    }
    return { tape: '', suite: suggestion };
  }

  // ----- Dialogue avec le greffier -----

  envoyer(texte = this.saisie(), comparer?: [string, string], action?: 'catalogue' | 'choisir_deux'): void {
    const p = this.persona();
    if (!p || this.enCours() || !texte.trim()) return;
    // Les questions précédentes partent avec la nouvelle : le greffier relit la conversation.
    const historique = this.messages().filter((m) => m.de === 'moi').map((m) => m.texte)
      .slice(this.debutContexte()).slice(-10);
    this.ajouter({ de: 'moi', texte: texte.trim() });
    this.saisie.set('');
    const champ = this.champ()?.nativeElement;
    if (champ) champ.value = '';
    this.ouverte.set(false);
    this.active.set(-1);
    this.enCours.set(true);

    const contexte = this.enAttente();
    // L'audience plaidée part avec la question : l'archiviste peut répondre sur le débat.
    const audience = this.tribunal.dossierAudience(p.cle);
    this.api.analyserQuestion({
      texte, profil: p.cle, ticker: contexte.ticker, taille: contexte.taille, comparer, action, historique, audience,
    }).subscribe({
      next: (a) => {
        this.enCours.set(false);
        if (a.statut === 'social' && a.motif === 'recommencer') {
          this.ajouter({ de: 'greffier', ton: 'question', texte: a.message });
          this.effacerContexte();
          this.ouverte.set(false);
          return;
        }
        if (a.agent === 'archiviste') {
          this.repondreArchiviste(a);
          champ?.focus();
          this.ouverte.set(false);
          return;
        }
        this.ajouter({
          de: 'greffier',
          texte: a.message,
          ton: a.statut === 'recevable' ? 'ok' : a.statut === 'refus' ? 'refus' : 'question',
          analyse: a,
        });
        if (a.statut === 'choix' && a.motif === 'part_manquante') {
          // Le titre est connu : on peut cliquer une part proposée ou en écrire une autre.
          this.enAttente.set({ ticker: a.ticker, taille: null, attente: 'part' });
        } else if (a.statut === 'incomplet') {
          this.enAttente.set({
            ticker: a.ticker,
            taille: a.taille,
            attente: a.motif === 'part_manquante' ? 'part' : a.motif === 'titre_manquant' ? 'titre' : null,
          });
        } else {
          this.enAttente.set({ ticker: null, taille: null, attente: null });
        }
        // Rendre le focus au champ sans recouvrir la réponse qui vient d'apparaître.
        champ?.focus();
        this.ouverte.set(false);
      },
      error: (e: unknown) => {
        this.enCours.set(false);
        const detail = e instanceof HttpErrorResponse && e.status === 0
          ? "L'API du tribunal ne répond pas. Vérifiez qu'elle est lancée."
          : e instanceof HttpErrorResponse && typeof e.error?.detail === 'string' ? e.error.detail : String(e);
        this.ajouter({ de: 'greffier', ton: 'erreur', texte: `Le greffe est fermé pour l'instant : ${detail}` });
      },
    });
  }

  /** L'archiviste répond; après une fiche ou une comparaison, le greffier propose un procès. */
  private repondreArchiviste(a: AnalyseQuestion): void {
    const message: Message = { de: 'archiviste', texte: a.message, analyse: { ...a, choix: [] } };
    if (a.statut === 'selection') {
      // Un domaine qui ne contient qu'un titre est coché d'avance.
      const depart = a.selection === 'un_par_groupe'
        ? a.groupes.map((g) => (g.titres.length === 1 ? g.titres[0].ticker : ''))
        : [];
      message.choisis = signal(depart);
    }
    this.ajouter(message);
    this.enAttente.set({ ticker: null, taille: null, attente: null });

    if (a.statut === 'fiche' && a.choix.length) {
      this.ajouter({
        de: 'greffier',
        ton: 'question',
        texte: `Voulez-vous soumettre ${a.nomTitre} (${a.ticker}) au tribunal ? Choisissez une part, ou écrivez la vôtre.`,
        analyse: { ...a, statut: 'choix', motif: 'part_manquante', agent: 'greffier', fiches: [] },
      });
      this.enAttente.set({ ticker: a.ticker, taille: null, attente: 'part' });
    }
    if (a.statut === 'comparaison' && a.choix.length) {
      this.ajouter({
        de: 'greffier',
        ton: 'question',
        texte: 'Lequel convient le mieux à votre profil ? C\'est au tribunal d\'en juger : soumettez un titre, ou opposez les deux dans un débat.',
        analyse: { ...a, statut: 'choix', motif: 'comparaison', agent: 'greffier', fiches: [] },
      });
    }
  }

  // ----- Choix des titres à comparer -----

  estChoisi(m: Message, ticker: string, groupe: number): boolean {
    const choisis = m.choisis?.() ?? [];
    return m.analyse?.selection === 'un_par_groupe' ? choisis[groupe] === ticker : choisis.includes(ticker);
  }

  basculer(m: Message, ticker: string, groupe: number): void {
    if (!m.choisis || !this.estDerniere(m)) return;
    if (m.analyse?.selection === 'un_par_groupe') {
      m.choisis.update((c) => c.map((t, i) => (i === groupe ? ticker : t)));
    } else {
      m.choisis.update((c) =>
        c.includes(ticker) ? c.filter((t) => t !== ticker) : [...c, ticker].slice(-2),
      );
    }
  }

  peutComparer(m: Message): boolean {
    const choisis = (m.choisis?.() ?? []).filter(Boolean);
    return choisis.length === 2 && choisis[0] !== choisis[1];
  }

  comparerSelection(m: Message): void {
    const [a, b] = (m.choisis?.() ?? []).filter(Boolean);
    if (!a || !b) return;
    const titres = (m.analyse?.groupes ?? []).flatMap((g) =>
      g.titres.map((t) => ({ ...t, nom: t.ticker.startsWith('MOY:')
        ? `la moyenne de ${g.nom.toLowerCase()}`.replace('de les ', 'des ').replace('de le ', 'du ')
        : t.nomTitre })));
    const nom = (x: string) => titres.find((t) => t.ticker === x)?.nom ?? x;
    this.envoyer(`Compare ${nom(a)} et ${nom(b)}`, [a, b]);
  }

  /** Boutons sous la conversation : le catalogue sans avoir à le demander. */
  voirTousLesTitres(): void {
    this.envoyer('Voir tous les titres', undefined, 'catalogue');
  }

  choisirDeuxTitres(): void {
    this.envoyer('Comparer deux titres', undefined, 'choisir_deux');
  }

  /** Duel : les deux dossiers proposés passent devant le tribunal, puis une règle fixe tranche. */
  peutDueler(a: AnalyseQuestion): boolean {
    const tickers = new Set(a.choix.map((c) => c.ticker));
    return (a.motif === 'comparaison' || a.motif === 'plusieurs_titres') && a.choix.length === 2 && tickers.size === 2;
  }

  /** Même part des deux côtés pour un duel équitable : celle de la question, sinon 10 %. */
  partDuel(a: AnalyseQuestion): number {
    const [x, y] = a.choix;
    return x && y && x.taille === y.taille ? x.taille : 0.1;
  }

  ouvrirDuel(a: AnalyseQuestion): void {
    const p = this.persona();
    if (!p || !this.peutDueler(a)) return;
    const [x, y] = a.choix;
    const part = this.partDuel(a);
    this.router.navigate(['/duel'], {
      queryParams: { profil: p.cle, a: `${x.ticker}:${part}`, b: `${y.ticker}:${part}` },
    });
  }

  voirFiche(ticker: string): void {
    this.envoyer(`Les chiffres de ${ticker}`);
  }

  reformuler(question: string): void {
    this.accepter(question);
    this.ouverte.set(false);
  }

  modifierPart(a: AnalyseQuestion): void {
    this.enAttente.set({ ticker: a.ticker, taille: null, attente: 'part' });
    this.ajouter({
      de: 'greffier',
      ton: 'question',
      texte: `Quelle part ${this.dePortefeuille()} voulez-vous placer dans ${a.nomTitre} (${a.ticker}) ? Jusqu’à 50 %.`,
    });
    this.ouverte.set(true);
    this.champ()?.nativeElement.focus();
  }

  ouvrirDebat(a: AnalyseQuestion | ChoixDossier): void {
    const p = this.persona();
    if (!p || !a.ticker || a.taille == null) return;
    this.sonAudience.amorcer();
    this.router.navigate(['/tribunal-2'], {
      queryParams: { profil: p.cle, ticker: a.ticker, taille: a.taille, question: a.question },
    });
  }

  // ----- Retour d'audience -----

  /** Le procès est encore en mémoire et l'investisseur n'a pas voté : il peut revenir voter. */
  peutRevenirVoter(au: AudienceSuspendue): boolean {
    const p = this.persona();
    return !!p && !this.tribunal.voteAudience() && this.tribunal.correspond(p.cle, au.ticker, au.taille);
  }

  revenirVoter(au: AudienceSuspendue): void {
    const p = this.persona();
    if (!p) return;
    this.router.navigate(['/tribunal-2'], {
      queryParams: { profil: p.cle, ticker: au.ticker, taille: au.taille, question: au.question || undefined, reprendre: 1 },
    });
  }

  interrogerArchiviste(au: AudienceSuspendue): void {
    const pr = this.tribunal.resultat();
    const fait = (motif: RegExp) => pr?.pieces.flatMap((x) => x.faits).find((f) => motif.test(f.libelle))?.valeur;
    const partRisque = fait(/part du risque/i);
    const pireBaisse = fait(/pire baisse observée, avec/i);
    this.ajouter({
      de: 'archiviste',
      texte: `Posez-moi une question sur le débat ${au.nomTitre} (${au.ticker}) : je réponds à partir des pièces `
        + 'scellées, sans trancher à votre place.',
      suggestions: [
        ...(partRisque ? [`D'où vient le ${partRisque} du Procureur ?`] : []),
        ...(pireBaisse ? [`D'où vient le ${pireBaisse} de pire baisse ?`] : []),
        'Sur quoi s\'appuie la Défense ?',
        'Que contient la pièce P-02 ?',
        'C\'est quoi la part du risque ?',
      ].slice(0, 4),
    });
    this.champ()?.nativeElement.focus();
  }

  /** Même titre, autre part : le chemin le plus court pour voir si le verdict bouge. */
  autresParts(au: AudienceSuspendue): number[] {
    return [0.05, 0.1, 0.2].filter((t) => Math.abs(t - au.taille) > 1e-9).slice(0, 2);
  }

  debatAutrePart(au: AudienceSuspendue, taille: number): void {
    this.ouvrirDebat({
      ticker: au.ticker, nomTitre: au.nomTitre, taille, raison: '',
      question: `Devrais-je placer ${Math.round(taille * 100)} % de mon portefeuille dans ${au.nomTitre} (${au.ticker}) ?`,
    });
  }

  estDerniere(m: Message): boolean {
    const liste = this.messages();
    return liste[liste.length - 1] === m;
  }

  private ajouter(m: Message): void {
    this.messages.update((liste) => [...liste, m]);
    setTimeout(() => {
      const fil = this.fil()?.nativeElement;
      fil?.scrollTo({ top: fil.scrollHeight, behavior: 'smooth' });
    });
  }
}
