"""Les votes des débats précédents : le greffier s'en souvient.

Le frontend envoie, avec chaque question, la liste des débats déjà votés dans la session
(procès d'un titre ou duel entre deux titres). L'archiviste les récapitule sur demande
(« qu'ai-je voté ? »), et le greffier les glisse dans le contexte donné à Bedrock.
Rien n'est inventé : chaque ligne vient d'un vote réellement rendu à l'écran.
"""
from __future__ import annotations

import re
import unicodedata

from .format import pct

DEMANDE = (
    r"\b(?:mes|nos) (?:votes?|verdicts?|debats?|proces|decisions?|choix)\b",
    r"\bqu'?(?:est-ce que )?j'?ai (?:vote|choisi|decide|tranche)",
    r"\bj'?ai vote\b", r"\bai-je vote\b", r"\bavais vote\b",
    r"\b(?:debats?|proces|duels?|audiences?) (?:precedents?|d'?avant|passes?)\b",
    r"\b(?:recap|recapitul|bilan|historique)\w*\b.*\b(?:votes?|debats?|proces|duels?|verdicts?)\b",
    r"\b(?:votes?|debats?|proces|duels?|verdicts?)\b.*\b(?:recap|recapitul|bilan|historique)\w*\b",
    r"\b(?:suis-je|etais-je) (?:d'?accord|coherent)\b", r"\bd'?accord avec le tribunal\b",
)


def _normaliser(texte: str) -> str:
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sans_accents.lower().replace("’", "'")).strip()


def demande_les_votes(texte: str) -> bool:
    norm = _normaliser(texte)
    return any(re.search(m, norm) for m in DEMANDE)


def _camp(v: dict) -> str:
    return "la Défense (pour la demande)" if v.get("vote") == "avocat_defense" else "le Procureur (contre la demande)"


def decrire(v: dict) -> str:
    """Une ligne lisible par l'investisseur, et par le modèle."""
    part = pct(float(v.get("taille") or 0), 0)
    if v.get("type") == "duel":
        a, b, choisi = v.get("ticker"), v.get("adversaire"), v.get("vote")
        ligne = f"{a} contre {b} ({part}) : vous avez voté pour {choisi}"
        gagnant = v.get("gagnant")
        if gagnant:
            ligne += ", le tribunal vous rejoint." if gagnant == choisi else f" ; le tribunal a retenu {gagnant}."
        else:
            ligne += " ; le tribunal n'a pas départagé les deux titres."
        return ligne
    ligne = f"{v.get('nomTitre') or v.get('ticker')} ({v.get('ticker')}, {part}) : vous avez suivi {_camp(v)}"
    verdict = v.get("verdictTribunal")
    if verdict:
        ligne += f" ; verdict du tribunal « {verdict} »"
        if v.get("accord") is True:
            ligne += ", même conclusion que vous."
        elif v.get("accord") is False:
            ligne += ", la conclusion inverse."
        else:
            ligne += "."
    else:
        ligne += "."
    return ligne


def bilan(votes: list[dict]) -> str:
    tranches = [v for v in votes if (v.get("accord") is not None if v.get("type") != "duel" else bool(v.get("gagnant")))]
    if not tranches:
        return ""
    accords = sum(1 for v in tranches
                  if (v.get("accord") is True if v.get("type") != "duel" else v.get("gagnant") == v.get("vote")))
    return f"Le tribunal a rejoint votre vote {accords} fois sur {len(tranches)}."


def repondre(votes: list[dict], nom: str) -> tuple[str, list[dict]]:
    """Le message de l'archiviste et les lignes à afficher, du plus ancien au plus récent."""
    if not votes:
        return (f"{nom} n'a encore voté dans aucun débat de cette session. Soumettez une décision au "
                "tribunal, puis rendez votre verdict : je garderai la trace de chaque vote."), []
    n = len(votes)
    message = f"Vous avez voté dans {n} débat{'s' if n > 1 else ''} de cette session. {bilan(votes)}".strip()
    return message, [{**v, "ligne": decrire(v)} for v in votes]


def pour_le_modele(votes: list[dict]) -> str:
    """Le contexte donné à Bedrock : une ligne par vote."""
    return "\n".join(f"- {'Duel' if v.get('type') == 'duel' else 'Procès'} {decrire(v)}" for v in votes) or "- (aucun)"
