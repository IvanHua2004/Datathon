"""L'archiviste répond aux questions sur une audience déjà plaidée.

Il ne lit que ce qui a été versé au dossier : les pièces scellées des témoins et le texte des
deux plaidoiries. Il dit d'où vient un chiffre, ce que contient une pièce, sur quoi s'appuie
chaque camp, et ce que veut dire un terme. Il ne dit jamais qui a gagné : c'est le verdict de
l'investisseur. Aucun appel à un modèle : tout est retrouvé dans le dossier, donc vérifiable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .conversation import GLOSSAIRE
from .questions import _normaliser

# Un nombre tel qu'écrit en français : -69 100, 37,6, 1,9 (espaces fines comprises).
_NOMBRE = re.compile(r"-?\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?|-?\d+(?:[.,]\d+)?")
_PIECE = re.compile(r"\bp\s*-?\s*0*(\d{1,2})\b")

_QUI_A_GAGNE = (
    r"qui (?:a|aurait) (?:gagne|raison)", r"qui gagne", r"qui a le mieux", r"le plus convaincant",
    r"pour qui (?:je dois |dois-je |devrais-je )?voter", r"je (?:dois|devrais) voter",
    r"meilleur (?:avocat|argument)", r"qui croire", r"lequel (?:a|avait) raison",
)
_DEFENSE = (r"\bdefense\b", r"\bvigor\b")
_ACCUSATION = (r"\bprocureur\b", r"\baccusation\b", r"\bausterer?\b")
_SUR_LE_DEBAT = (
    r"\bdebat\b", r"\baudience\b", r"\bplaidoirie", r"\bpiece", r"\btemoin", r"\bavocat",
    r"\bargument", r"\bgreffier d'audience\b", *_DEFENSE, *_ACCUSATION,
)


@dataclass
class Reponse:
    message: str
    extraits: list[dict] = field(default_factory=list)   # pièces citées, pour les afficher en fiche


def _nombres(texte: str) -> list[float]:
    valeurs = []
    for brut in _NOMBRE.findall(texte):
        propre = re.sub(r"[   ]", "", brut).replace(",", ".")
        try:
            valeurs.append(float(propre))
        except ValueError:
            continue
    return valeurs


def _meme_nombre(a: float, b: float) -> bool:
    return abs(abs(a) - abs(b)) < 0.051


def _minuscule(texte: str) -> str:
    return texte[:1].lower() + texte[1:]


def _camp(plaidoirie: dict) -> str:
    role = _normaliser(plaidoirie.get("role", "") + " " + plaidoirie.get("camp", ""))
    return "accusation" if re.search(r"procureur|accusation", role) else "defense"


def _nom_camp(camp: str) -> str:
    return "la Défense" if camp == "defense" else "le Procureur"


def _extrait(piece: dict, faits: list[dict] | None = None) -> dict:
    return {
        "numero": piece.get("numero", ""),
        "temoin": piece.get("temoin", ""),
        "description": piece.get("description", ""),
        "faits": (faits if faits is not None else piece.get("faits", []))[:6],
        "source": piece.get("source", ""),
        "periode": piece.get("periode", ""),
        "limites": piece.get("limites", ""),
    }


_NOUVELLE_DEMANDE = re.compile(r"\b(?:placer|mettre|investir|acheter|ajouter|devrais-je|dois-je|et (?:avec|si|pour))\b")


def concerne_le_debat(texte: str, audience: dict) -> bool:
    """Vrai si la question porte sur l'audience plaidée plutôt que sur une nouvelle demande."""
    norm = _normaliser(texte)
    if _NOUVELLE_DEMANDE.search(norm):
        return False
    if any(re.search(m, norm) for m in (*_SUR_LE_DEBAT, *_QUI_A_GAGNE)) or _PIECE.search(norm):
        return True
    # Un terme du glossaire qui figure dans les pièces (« c'est quoi la part du risque ? »).
    libelles = " ".join(_normaliser(f["libelle"]) for p in audience.get("pieces", []) for f in p.get("faits", []))
    for terme, (motifs, _) in GLOSSAIRE.items():
        mots = re.findall(r"[a-z]{4,}", _normaliser(terme))
        if mots and any(re.search(mo, norm) for mo in motifs) and all(w in libelles for w in mots):
            return True
    # Un chiffre cité dans une pièce ou une plaidoirie (« d'où vient le 37,6 % ? »).
    cites = _nombres(" ".join(f["valeur"] for p in audience.get("pieces", []) for f in p.get("faits", [])))
    cites += _nombres(" ".join(p.get("texte", "") for p in audience.get("plaidoiries", [])))
    if any(_meme_nombre(n, c) for n in _nombres(texte) if abs(n) >= 1 or "," in texte for c in cites):
        return re.search(r"d'?ou|vient|pourquoi|vrai|exact|correct|signifie|veut dire|c'?est quoi|ce chiffre", norm) is not None
    return False


def repondre(texte: str, audience: dict) -> Reponse:
    norm = _normaliser(texte)
    pieces = audience.get("pieces", [])
    plaidoiries = audience.get("plaidoiries", [])
    titre = audience.get("ticker", "le titre")

    # 1. Qui a gagné ? Ce n'est pas à l'archiviste de le dire.
    if any(re.search(m, norm) for m in _QUI_A_GAGNE):
        lignes = []
        for p in plaidoiries:
            cites = sorted(set(re.findall(r"\[P-\d+\]", p.get("texte", ""))))
            lignes.append(f"{_nom_camp(_camp(p))} s'appuie sur {', '.join(cites) or 'aucune pièce citée'}")
        return Reponse(
            "Je ne tranche pas : le verdict vous revient, et la décision du tribunal reste scellée jusqu'à votre vote. "
            + (("Pour vérifier : " + " ; ".join(lignes) + ". ") if lignes else "")
            + "Demandez-moi d'où vient un chiffre, ou ce que contient une pièce, pour vérifier chaque argument.")

    # 2. Une pièce nommée : « que contient P-02 ? ».
    m = _PIECE.search(norm)
    if m:
        numero = f"P-{int(m.group(1)):02d}"
        piece = next((p for p in pieces if p.get("numero") == numero), None)
        if piece is None:
            return Reponse(f"Aucune pièce {numero} n'a été versée au dossier. Pièces disponibles : "
                           + ", ".join(f"{p['numero']} ({p.get('temoin', '')})" for p in pieces) + ".")
        return Reponse(f"La pièce {numero} est la déposition du témoin « {piece.get('temoin', '')} » : "
                       f"{piece.get('description', '')}. Voici ses principaux faits.", [_extrait(piece)])

    # 3. Un chiffre : d'où vient-il, et qui l'a cité ?
    demandes = [n for n in _nombres(texte) if not (0 < abs(n) < 1 and "," not in texte)]
    if demandes:
        trouves = []
        for piece in pieces:
            faits = [f for f in piece.get("faits", []) if any(_meme_nombre(n, v) for n in demandes for v in _nombres(f["valeur"]))]
            if faits:
                trouves.append(_extrait(piece, faits))
        camps = [_nom_camp(_camp(p)) for p in plaidoiries
                 if any(_meme_nombre(n, v) for n in demandes for v in _nombres(p.get("texte", "")))]
        brut = re.search(rf"(?:{_NOMBRE.pattern})(?:\s*(?:%|\$|ans?\b))?", texte)
        chiffre = brut.group(0).strip() if brut else str(demandes[0])
        if trouves:
            premier = trouves[0]
            fait = premier["faits"][0]
            qui = f" Il est cité par {' et '.join(dict.fromkeys(camps))}." if camps else ""
            return Reponse(
                f"« {chiffre} » vient de la pièce {premier['numero']} (témoin « {premier['temoin']} ») : "
                f"{_minuscule(fait['libelle'])} = {fait['valeur']}.{qui} "
                f"Ce chiffre est observé sur la période {premier['periode'] or 'du jeu de données'} : c'est le passé, pas une prévision.",
                trouves)
        if camps:
            return Reponse(
                f"« {chiffre} » apparaît dans la plaidoirie de {' et de '.join(dict.fromkeys(camps))}, mais dans aucune "
                "pièce scellée : il n'est pas vérifié par le greffier. Il peut s'agir d'un calcul de l'avocat à partir des pièces.")
        return Reponse(f"Je ne trouve « {chiffre} » ni dans les pièces ni dans les plaidoiries de cette audience.")

    # 4. Un terme du glossaire, appliqué aux chiffres de l'audience.
    for terme, (motifs, definition) in GLOSSAIRE.items():
        if any(re.search(mo, norm) for mo in motifs):
            mots = [w for w in re.findall(r"[a-z]{4,}", _normaliser(terme))]
            lies = []
            for piece in pieces:
                faits = [f for f in piece.get("faits", []) if all(w in _normaliser(f["libelle"]) for w in mots)]
                if faits:
                    lies.append(_extrait(piece, faits))
            suite = " Dans cette audience :" if lies else ""
            return Reponse(f"{definition}{suite}", lies)

    # 5. Un camp : « qu'a dit la défense ? », « sur quoi s'appuie le procureur ? ».
    for camp, motifs in (("defense", _DEFENSE), ("accusation", _ACCUSATION)):
        if any(re.search(mo, norm) for mo in motifs):
            plaidoirie = next((p for p in plaidoiries if _camp(p) == camp), None)
            if plaidoirie is None:
                break
            cites = sorted(set(re.findall(r"\[(P-\d+)\]", plaidoirie.get("texte", ""))))
            non_verifies = plaidoirie.get("non_verifies") or plaidoirie.get("nonVerifies") or []
            extraits = [_extrait(p) for p in pieces if p.get("numero") in cites]
            controle = (f" Le greffier signale des chiffres absents des pièces : {', '.join(non_verifies)}."
                        if non_verifies else " Tous ses chiffres se retrouvent dans les pièces scellées.")
            return Reponse(
                f"{_nom_camp(camp).capitalize()} plaide {'pour' if camp == 'defense' else 'contre'} la demande sur {titre} "
                f"et s'appuie sur {', '.join(cites) or 'aucune pièce citée'}.{controle}", extraits)

    # 6. Par défaut : le sommaire du dossier.
    return Reponse(
        "Voici les pièces versées au dossier de cette audience. Demandez-moi d'où vient un chiffre "
        "(« d'où vient 37,6 % ? »), ce que contient une pièce (« que dit P-02 ? ») ou sur quoi s'appuie un camp.",
        [_extrait(p, p.get("faits", [])[:3]) for p in pieces])
