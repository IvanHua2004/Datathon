"""Dictée vocale de l'investisseur avec Amazon Transcribe (streaming, fr-CA, us-east-1).

Le navigateur envoie le micro en PCM 16 bits, 16 kHz, par WebSocket ; on relaie l'audio à
Transcribe et on renvoie le texte au fur et à mesure (provisoire, puis final). Un vocabulaire
personnalisé apprend à Transcribe les noms des 31 titres (« Couche-Tard », « S.P.Y. »…) : sans lui,
les tickers sont presque toujours mal transcrits.

Sans identifiants AWS ou sans accès, on répond « indisponible » tout de suite : l'interface bascule
alors sur la dictée du navigateur.
"""

from __future__ import annotations

import logging
import os
import re
import threading

log = logging.getLogger(__name__)

REGION = os.environ.get("AWS_REGION", "us-east-1")
LANGUE = "fr-CA"
FREQUENCE_HZ = 16_000
NOM_VOCABULAIRE = "rdc-titres-fr-ca"

# Ce que l'investisseur dit à voix haute pour les titres de l'univers. Les sigles s'écrivent avec des
# points (« S.P.Y. ») : c'est la convention de Transcribe pour qu'il les épelle lettre par lettre.
PHRASES = [
    "Shopify", "Couche-Tard", "Enbridge", "Fortis", "Manuvie", "Manulife", "Constellation", "Canadien-National",
    "Banque-Royale", "Toronto-Dominion", "Apple", "Microsoft", "Nvidia", "Alphabet", "Amazon", "Tesla",
    "JPMorgan", "Johnson-and-Johnson", "Procter-and-Gamble", "Exxon", "Bitcoin", "Ether", "Ethereum",
    "S.P.Y.", "Q.Q.Q.", "X.I.U.", "X.B.B.", "Z.S.T.", "A.G.G.", "T.L.T.", "G.L.D.", "E.S.G.V.",
    "F.N.B.", "E.T.F.", "E.S.G.", "cryptoactif", "cryptoactifs", "portefeuille",
]

_etat_vocabulaire: dict[str, str | None] = {"nom": None, "verifie": None}
_verrou = threading.Lock()


def identifiants_presents() -> bool:
    try:
        import boto3
        return boto3.Session().get_credentials() is not None
    except Exception:  # boto3 absent ou configuration illisible
        return False


def vocabulaire_pret() -> str | None:
    """Le nom du vocabulaire s'il est prêt ; le crée au premier appel (il met quelques minutes à l'être).

    Jamais bloquant pour la dictée : en cas de souci (droits, validation), on dicte sans vocabulaire.
    """
    with _verrou:
        if _etat_vocabulaire["verifie"] == "READY":
            return _etat_vocabulaire["nom"]
        try:
            import boto3
            client = boto3.client("transcribe", region_name=REGION)
            try:
                etat = client.get_vocabulary(VocabularyName=NOM_VOCABULAIRE)["VocabularyState"]
            except client.exceptions.NotFoundException:
                client.create_vocabulary(VocabularyName=NOM_VOCABULAIRE, LanguageCode=LANGUE, Phrases=PHRASES)
                etat = "PENDING"
            _etat_vocabulaire["verifie"] = etat
            _etat_vocabulaire["nom"] = NOM_VOCABULAIRE if etat == "READY" else None
            if etat == "FAILED":
                log.warning("Vocabulaire Transcribe en échec : dictée sans vocabulaire personnalisé.")
        except Exception as erreur:  # AccessDenied, réseau…
            log.info("Vocabulaire Transcribe indisponible : %s", erreur)
            _etat_vocabulaire["verifie"] = "INDISPONIBLE"
            _etat_vocabulaire["nom"] = None
        return _etat_vocabulaire["nom"]


_SIGLE = re.compile(r"\b((?:[A-Za-z]\.){2,})")


def nettoyer(texte: str) -> str:
    """« S.P.Y. » -> « SPY », pour que le greffier reconnaisse le ticker."""
    return _SIGLE.sub(lambda m: m.group(1).replace(".", "").upper(), texte).strip()
