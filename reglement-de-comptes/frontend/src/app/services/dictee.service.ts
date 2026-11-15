import { Injectable, NgZone, computed, inject, signal } from '@angular/core';

/** Qui transcrit : Amazon Transcribe (via l'API) ou, en secours, la dictée du navigateur. */
export type MoteurDictee = 'transcribe' | 'navigateur';
export type EtatDictee = 'inactif' | 'connexion' | 'ecoute';

export interface RappelsDictee {
  /** Texte complet de la dictée en cours ; `provisoire` tant que la phrase n'est pas fixée. */
  texte(texte: string, provisoire: boolean): void;
  /** Fin de l'écoute (silence, clic sur le micro, erreur). */
  fin?(): void;
}

const FREQUENCE_TRANSCRIBE = 16_000;
const DELAI_CONNEXION_MS = 3_000;
const SILENCE_MS = 2_200;
const DUREE_MAX_MS = 45_000;
const SEUIL_SILENCE = 0.012;

/** Petit processeur audio : renvoie chaque bloc du micro au fil principal. */
const CODE_CAPTEUR = `
class Capteur extends AudioWorkletProcessor {
  process(entrees) {
    const canal = entrees[0] && entrees[0][0];
    if (canal) this.port.postMessage(canal.slice(0));
    return true;
  }
}
registerProcessor('rdc-capteur', Capteur);
`;

interface ReconnaissanceVocale {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((e: { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}

/**
 * Dictée vocale des barres de saisie. On tente Amazon Transcribe (fr-CA, vocabulaire des 31 titres) ;
 * s'il est indisponible (pas d'identifiants AWS, pas d'accès, réseau), on bascule sur la reconnaissance
 * vocale du navigateur. Le texte n'est jamais envoyé automatiquement : on le relit avant d'appuyer sur Entrée.
 */
@Injectable({ providedIn: 'root' })
export class DicteeService {
  private readonly zone = inject(NgZone);

  readonly etat = signal<EtatDictee>('inactif');
  readonly moteur = signal<MoteurDictee | null>(null);
  readonly erreur = signal('');
  readonly actif = computed(() => this.etat() !== 'inactif');

  private readonly Reconnaissance: (new () => ReconnaissanceVocale) | undefined =
    typeof window === 'undefined' ? undefined
      : ((window as unknown as Record<string, unknown>)['SpeechRecognition']
        ?? (window as unknown as Record<string, unknown>)['webkitSpeechRecognition']) as (new () => ReconnaissanceVocale) | undefined;
  /** Le micro est utilisable d'une façon ou d'une autre dans ce navigateur. */
  readonly disponible = typeof navigator !== 'undefined'
    && (!!navigator.mediaDevices?.getUserMedia || !!this.Reconnaissance);

  private rappels?: RappelsDictee;
  private fixe = '';
  private ws?: WebSocket;
  private flux?: MediaStream;
  private contexte?: AudioContext;
  private reconnaissance?: ReconnaissanceVocale;
  private minuterieSilence?: ReturnType<typeof setTimeout>;
  private minuterieMax?: ReturnType<typeof setTimeout>;
  private aParle = false;
  /** Pourquoi Transcribe n'a pas pris la dictée (affiché si le secours échoue aussi). */
  private raisonTranscribe = '';

  demarrer(rappels: RappelsDictee): void {
    if (this.actif()) return;
    this.rappels = rappels;
    this.fixe = '';
    this.aParle = false;
    this.erreur.set('');
    this.raisonTranscribe = '';
    this.etat.set('connexion');
    this.essayerTranscribe();
  }

  arreter(): void {
    if (!this.actif()) return;
    if (this.ws?.readyState === WebSocket.OPEN) {
      // On laisse Transcribe finir la dernière phrase : le serveur ferme après « termine ».
      this.couperMicro();
      this.ws.send('fin');
      setTimeout(() => this.terminer(), 1_500);
      return;
    }
    this.reconnaissance?.stop();
    this.terminer();
  }

  // ----- Amazon Transcribe, par l'API -----

  private essayerTranscribe(): void {
    if (!navigator.mediaDevices?.getUserMedia || typeof AudioWorkletNode === 'undefined') {
      this.essayerNavigateur();
      return;
    }
    const url = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/dictee`;
    let ws: WebSocket;
    try {
      ws = new WebSocket(url);
    } catch {
      this.essayerNavigateur();
      return;
    }
    this.ws = ws;
    ws.binaryType = 'arraybuffer';
    let pret = false;
    const delai = setTimeout(() => {
      if (pret) return;
      this.raisonTranscribe = 'l’API ne répond pas à temps';
      this.basculerSurNavigateur();
    }, DELAI_CONNEXION_MS);

    ws.onmessage = (e) => this.zone.run(() => {
      const m = JSON.parse(String(e.data)) as { type: string; texte?: string; detail?: string };
      if (m.type === 'pret') {
        pret = true;
        clearTimeout(delai);
        void this.ouvrirMicro();
      } else if (m.type === 'indisponible') {
        clearTimeout(delai);
        this.raisonTranscribe = expliquer(m.detail);
        if (pret && this.fixe) this.terminer(); else this.basculerSurNavigateur();
      } else if (m.type === 'partiel' || m.type === 'final') {
        this.recevoir(m.texte ?? '', m.type === 'partiel');
      } else if (m.type === 'termine') {
        this.terminer();
      }
    });
    ws.onerror = () => this.zone.run(() => {
      if (pret) return;
      clearTimeout(delai);
      this.raisonTranscribe ||= 'connexion à l’API impossible';
      this.basculerSurNavigateur();
    });
    ws.onclose = () => this.zone.run(() => { if (pret) this.terminer(); });
  }

  private async ouvrirMicro(): Promise<void> {
    try {
      this.flux = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
    } catch {
      this.ws?.close();
      this.echouer('Autorisez le micro (icône dans la barre d’adresse), puis réessayez.');
      return;
    }
    const contexte = new AudioContext();
    this.contexte = contexte;
    const url = URL.createObjectURL(new Blob([CODE_CAPTEUR], { type: 'application/javascript' }));
    await contexte.audioWorklet.addModule(url);
    URL.revokeObjectURL(url);
    const source = contexte.createMediaStreamSource(this.flux);
    const capteur = new AudioWorkletNode(contexte, 'rdc-capteur');
    let tampon: number[] = [];
    capteur.port.onmessage = (e: MessageEvent<Float32Array>) => {
      const bloc = reechantillonner(e.data, contexte.sampleRate, FREQUENCE_TRANSCRIBE);
      tampon.push(...bloc);
      this.surveillerSilence(e.data);
      // Environ 100 ms d'audio par message.
      if (tampon.length >= FREQUENCE_TRANSCRIBE / 10 && this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(enPcm16(tampon));
        tampon = [];
      }
    };
    source.connect(capteur);
    this.moteur.set('transcribe');
    this.etat.set('ecoute');
    this.minuterieMax = setTimeout(() => this.zone.run(() => this.arreter()), DUREE_MAX_MS);
  }

  /** Arrêt automatique après un silence, une fois que la personne a parlé. */
  private surveillerSilence(bloc: Float32Array): void {
    let somme = 0;
    for (const x of bloc) somme += x * x;
    const niveau = Math.sqrt(somme / bloc.length);
    if (niveau > SEUIL_SILENCE) {
      this.aParle = true;
      clearTimeout(this.minuterieSilence);
      this.minuterieSilence = undefined;
    } else if (this.aParle && !this.minuterieSilence) {
      this.minuterieSilence = setTimeout(() => this.zone.run(() => this.arreter()), SILENCE_MS);
    }
  }

  private basculerSurNavigateur(): void {
    this.ws?.close();
    this.ws = undefined;
    this.couperMicro();
    this.essayerNavigateur();
  }

  // ----- Dictée du navigateur (secours) -----

  private essayerNavigateur(): void {
    if (!this.Reconnaissance) {
      this.echouer(`La dictée n’est pas disponible. Amazon Transcribe : ${this.raisonTranscribe || 'indisponible'}. `
        + 'Et ce navigateur n’a pas de dictée intégrée (essayez Chrome ou Edge).');
      return;
    }
    const r = new this.Reconnaissance();
    this.reconnaissance = r;
    r.lang = 'fr-CA';
    r.interimResults = true;
    r.continuous = false;
    r.onresult = (e) => this.zone.run(() => {
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const resultat = e.results[i];
        this.recevoir(resultat[0].transcript, !resultat.isFinal);
      }
    });
    r.onerror = (e) => this.zone.run(() => {
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
        this.echouer('Autorisez le micro (icône dans la barre d’adresse), puis réessayez.');
      } else if (e.error === 'no-speech') {
        this.echouer('Je n’ai rien entendu. Appuyez sur le micro et parlez.');
      } else if (e.error !== 'aborted') {
        this.echouer('La dictée s’est interrompue. Réessayez, ou tapez votre question.');
      }
    });
    r.onend = () => this.zone.run(() => this.terminer());
    try {
      r.start();
      this.moteur.set('navigateur');
      this.etat.set('ecoute');
    } catch {
      this.echouer('La dictée n’a pas pu démarrer. Réessayez, ou tapez votre question.');
    }
  }

  // ----- Commun -----

  private recevoir(texte: string, provisoire: boolean): void {
    const morceau = texte.trim();
    if (!morceau) return;
    if (provisoire) {
      this.rappels?.texte(joindre(this.fixe, morceau), true);
    } else {
      this.fixe = joindre(this.fixe, morceau);
      this.rappels?.texte(this.fixe, false);
    }
  }

  private couperMicro(): void {
    clearTimeout(this.minuterieSilence);
    clearTimeout(this.minuterieMax);
    this.minuterieSilence = undefined;
    this.flux?.getTracks().forEach((piste) => piste.stop());
    this.flux = undefined;
    void this.contexte?.close();
    this.contexte = undefined;
  }

  private echouer(message: string): void {
    this.erreur.set(message);
    this.terminer();
  }

  private terminer(): void {
    if (this.etat() === 'inactif') return;
    this.couperMicro();
    this.ws?.close();
    this.ws = undefined;
    this.reconnaissance = undefined;
    if (this.fixe) this.rappels?.texte(this.fixe, false);
    this.etat.set('inactif');
    const rappels = this.rappels;
    this.rappels = undefined;
    rappels?.fin?.();
  }
}

/** La raison renvoyée par l'API, en mots simples. */
function expliquer(detail?: string): string {
  if (!detail) return 'indisponible';
  if (/identifiant/i.test(detail) || /NoCredentials|ExpiredToken|Unrecognized/i.test(detail)) {
    return 'aucun identifiant AWS valide côté API (refaites les « export » puis relancez docker compose up)';
  }
  if (/AccessDenied|Forbidden|NotAuthorized/i.test(detail)) return 'accès refusé par AWS';
  if (/ModuleNotFound|ImportError/i.test(detail)) return 'paquet amazon-transcribe absent (relancez avec --build)';
  return detail;
}

function joindre(a: string, b: string): string {
  return a ? `${a} ${b}` : b;
}

/** Ramène le micro (souvent 48 kHz) à 16 kHz, en moyennant les échantillons de chaque fenêtre. */
function reechantillonner(bloc: Float32Array, depart: number, arrivee: number): number[] {
  if (depart === arrivee) return Array.from(bloc);
  const rapport = depart / arrivee;
  const sortie: number[] = [];
  for (let i = 0; i < Math.floor(bloc.length / rapport); i++) {
    const debut = Math.floor(i * rapport);
    const fin = Math.min(bloc.length, Math.floor((i + 1) * rapport));
    let somme = 0;
    for (let j = debut; j < fin; j++) somme += bloc[j];
    sortie.push(somme / Math.max(1, fin - debut));
  }
  return sortie;
}

/** PCM 16 bits petit-boutiste, le format attendu par Transcribe. */
function enPcm16(echantillons: number[]): ArrayBuffer {
  const vue = new DataView(new ArrayBuffer(echantillons.length * 2));
  echantillons.forEach((x, i) => {
    const borne = Math.max(-1, Math.min(1, x));
    vue.setInt16(i * 2, borne < 0 ? borne * 0x8000 : borne * 0x7fff, true);
  });
  return vue.buffer;
}
