"""Le greffier : numérote chaque dépôt de témoin comme une pièce et vérifie les textes.

Règle : un chiffre cité par un agent doit figurer dans une pièce (ou dans le profil).
Les chiffres introuvables sont signalés à l'écran comme « non vérifiés ».
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

_NOMBRE = re.compile(r"\d[\d\s  ]*(?:[.,]\d+)?")


def _normaliser(texte: str) -> str:
    return re.sub(r"[\s  ]", "", texte).replace(",", ".").rstrip(".")


def nombres_dans(texte: str) -> set[str]:
    return {_normaliser(m.group()) for m in _NOMBRE.finditer(texte)} - {""}


@dataclass
class Piece:
    numero: str
    temoin: str
    outil: str
    parametres: dict
    faits: dict[str, str]          # libellé -> valeur déjà mise en forme
    source: str
    periode: str
    limites: str
    appele_par: str
    horodatage: str

    def en_texte(self) -> str:
        lignes = [f"[{self.numero}] Témoin {self.temoin} (convoqué par {self.appele_par})"]
        lignes += [f"- {k} : {v}" for k, v in self.faits.items()]
        lignes += [f"Source : {self.source}", f"Période : {self.periode}", f"Limites : {self.limites}"]
        return "\n".join(lignes)


@dataclass
class Greffier:
    pieces: list[Piece] = field(default_factory=list)
    nombres_admis: set[str] = field(default_factory=set)   # chiffres du profil et de la demande

    def deposer(self, *, temoin: str, outil: str, parametres: dict, faits: dict[str, str],
                source: str, periode: str, limites: str, appele_par: str) -> Piece:
        for p in self.pieces:                       # un témoin ne dépose qu'une fois
            if p.temoin == temoin:
                return p
        piece = Piece(
            numero=f"P-{len(self.pieces) + 1:02d}", temoin=temoin, outil=outil,
            parametres=parametres, faits=faits, source=source, periode=periode,
            limites=limites, appele_par=appele_par,
            horodatage=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self.pieces.append(piece)
        return piece

    def admettre(self, *textes: str) -> None:
        for t in textes:
            self.nombres_admis |= nombres_dans(t)

    def chiffres_verifiables(self) -> set[str]:
        connus = set(self.nombres_admis)
        for p in self.pieces:
            connus |= nombres_dans(p.numero)
            for libelle, valeur in p.faits.items():
                connus |= nombres_dans(libelle) | nombres_dans(valeur)
            connus |= nombres_dans(p.periode)
        return connus

    def verifier(self, texte: str) -> list[str]:
        """Retourne les chiffres du texte qui ne figurent dans aucune pièce."""
        connus = self.chiffres_verifiables()
        return sorted(n for n in nombres_dans(texte) if n not in connus)
