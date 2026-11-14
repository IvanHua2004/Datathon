import { HttpErrorResponse } from '@angular/common/http';
import {
  Component, ElementRef, WritableSignal, computed, effect, inject, input, signal, viewChild,
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { EnteteComponent } from '../../components/entete/entete.component';
import { AnalyseQuestion, ChoixDossier } from '../../models/question.model';
import { ApiService } from '../../services/api.service';
import { ProcesService } from '../../services/proces.service';
import { Attente, completer } from '../../shared/autocompletion';
import { pct } from '../../shared/format';

interface Message {
  de: 'greffier' | 'archiviste' | 'moi';
  texte: string;
  ton?: 'ok' | 'refus' | 'question' | 'erreur';
  analyse?: AnalyseQuestion;
  /** Titres cochés quand l'archiviste fait choisir deux titres à comparer. */
  choisis?: WritableSignal<string[]>;
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
  private readonly router = inject(Router);
  readonly tribunal = inject(ProcesService);
  readonly pct = pct;

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

  private readonly fil = viewChild<ElementRef<HTMLElement>>('fil');
  private readonly champ = viewChild<ElementRef<HTMLInputElement>>('champ');

  readonly persona = computed(() => this.tribunal.profils().find((p) => p.cle === this.profil()) ?? null);

  readonly suggestions = computed(() => {
    const p = this.persona();
    if (!p || this.enCours()) return [];
    // Champ vide : on propose des débuts de phrase seulement au premier échange ou quand
    // le greffier attend une réponse précise (la part, le titre).
    const dejaParle = this.messages().some((m) => m.de === 'moi');
    const derniere = this.messages().at(-1);
    const choixAffiches = !!derniere?.analyse?.choix?.length;
    if (!this.saisie().trim() && dejaParle && (!this.enAttente().attente || choixAffiches)) return [];
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
        this.router.navigate(['/persona']);
      }
    });

    // Le greffier ouvre l'audience dès que le persona est connu.
    effect(() => {
      const p = this.persona();
      if (p && this.messages().length === 0) {
        this.messages.set([{
          de: 'greffier',
          ton: 'question',
          texte: `Bonjour ${p.nom}. Quelle décision voulez-vous soumettre au tribunal ? `
            + 'Nommez un titre et la part de votre portefeuille.',
        }]);
        setTimeout(() => this.champ()?.nativeElement.focus());
      }
    });
  }

  // ----- Saisie et suggestions -----

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

  envoyer(texte = this.saisie()): void {
    const p = this.persona();
    if (!p || this.enCours() || !texte.trim()) return;
    this.ajouter({ de: 'moi', texte: texte.trim() });
    this.saisie.set('');
    const champ = this.champ()?.nativeElement;
    if (champ) champ.value = '';
    this.ouverte.set(false);
    this.enCours.set(true);

    const contexte = this.enAttente();
    this.api.analyserQuestion({ texte, profil: p.cle, ticker: contexte.ticker, taille: contexte.taille }).subscribe({
      next: (a) => {
        this.enCours.set(false);
        if (a.agent === 'archiviste') {
          this.repondreArchiviste(a);
          this.ouverte.set(false);
          champ?.focus();
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
        // Les suggestions réapparaissent dès qu'on tape, sans cacher la réponse du greffier.
        this.ouverte.set(false);
        champ?.focus();
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
        texte: 'Lequel convient à votre profil ? C\'est au tribunal d\'en juger. Choisissez le titre à lui soumettre.',
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
    if (a && b) this.envoyer(`Compare ${a} et ${b}`);
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
      texte: `Quelle part de votre portefeuille voulez-vous placer dans ${a.nomTitre} (${a.ticker}) ? Jusqu’à 50 %.`,
    });
    this.ouverte.set(true);
    this.champ()?.nativeElement.focus();
  }

  ouvrirDebat(a: AnalyseQuestion | ChoixDossier): void {
    const p = this.persona();
    if (!p || !a.ticker || a.taille == null) return;
    this.router.navigate(['/tribunal'], {
      queryParams: { profil: p.cle, ticker: a.ticker, taille: a.taille, question: a.question },
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
