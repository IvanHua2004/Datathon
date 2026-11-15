interface Voix {
  fichier: string;
  vitesse: number;
}

function voix(nom: string, vitesse = 1): Voix {
  return { fichier: 'assets/tribunal-2/voix/' + nom, vitesse };
}

const VOIX_AVOCATS = [
  voix('angry1.ogg'),
  voix('angry2.ogg'),
  // Version grave du second extrait pour que les deux variantes restent reconnaissables.
  voix('angry2.mp3', 0.78),
];

const VOIX_PARTICIPANTS: Record<string, Voix> = {
  huissier: voix('cartoon-phone-gibberish.mp3'),
  greffier: voix('cheerful-mumble-short.ogg'),
  temoin: voix('tiny-voice-sad.ogg'),
  juge: voix('talking-speak-gibberish-00001.mp3'),
};

export function choisirVoixAudience(): Record<string, Voix> {
  const defense = Math.floor(Math.random() * VOIX_AVOCATS.length);
  const decalage = 1 + Math.floor(Math.random() * (VOIX_AVOCATS.length - 1));
  return {
    ...VOIX_PARTICIPANTS,
    avocat_defense: VOIX_AVOCATS[defense],
    procureur: VOIX_AVOCATS[(defense + decalage) % VOIX_AVOCATS.length],
  };
}
