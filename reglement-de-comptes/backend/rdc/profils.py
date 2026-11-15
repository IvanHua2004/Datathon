"""Profils d'investisseurs FICTIFS, inspirés des trois personas du cas officiel.

Les traits (âge, horizon, tolérance, préférences) viennent du cas. Tout ce qui est
chiffré ici (capital, budget de perte, plafonds, portefeuille de départ) est une
HYPOTHÈSE de l'équipe, à ajuster et à documenter. Aucune donnée réelle de client.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class Profil:
    cle: str
    nom: str
    resume: str
    objectif: str
    capital: float                 # en CAD (hypothèse)
    horizon_ans: float             # vient du cas (borne basse de la fourchette)
    budget_perte: float            # perte maximale supportable, fraction du capital (hypothèse)
    plafond_position: float        # poids maximal d'un seul titre individuel (hypothèse)
    plafond_secteur: float         # poids maximal d'un secteur (hypothèse)
    classes_exclues: tuple[str, ...] = ()
    filtre_esg: bool = False
    secteurs_a_justifier: tuple[str, ...] = ()   # exigent une preuve ESG avant d'entrer
    preferences: str = ""
    portefeuille: dict[str, float] = field(default_factory=dict)
    demande_exemple: tuple[str, float] = ("NVDA", 0.20)

    def avec(self, **changements) -> "Profil":
        return replace(self, **changements)

    @property
    def esg_strict(self) -> bool:
        """Conforme Roadmap Issue 1.3."""
        return self.filtre_esg

    @property
    def crypto_allowed(self) -> bool:
        """Conforme Roadmap Issue 1.3."""
        return "crypto" not in self.classes_exclues

    @property
    def horizon_max(self) -> float:
        """Conforme Roadmap Issue 1.3."""
        if self.cle == "amira":
            return 25.0
        elif self.cle == "mateo":
            return 12.0
        return 5.0

    @property
    def risque(self) -> str:
        """Conforme Roadmap Issue 1.3."""
        if self.cle == "amira":
            return "élevé"
        elif self.cle == "mateo":
            return "modéré"
        return "faible à modéré"

    def to_dict(self) -> dict:
        """Retourne un dictionnaire des contraintes lisible par les agents LLM."""
        return {
            "cle": self.cle,
            "nom": self.nom,
            "resume": self.resume,
            "objectif": self.objectif,
            "capital": self.capital,
            "horizon_ans": self.horizon_ans,
            "horizon_max": self.horizon_max,
            "budget_perte": self.budget_perte,
            "plafond_position": self.plafond_position,
            "plafond_secteur": self.plafond_secteur,
            "classes_exclues": list(self.classes_exclues),
            "crypto_allowed": self.crypto_allowed,
            "filtre_esg": self.filtre_esg,
            "esg_strict": self.esg_strict,
            "risque": self.risque,
            "secteurs_a_justifier": list(self.secteurs_a_justifier),
            "preferences": self.preferences,
            "portefeuille": dict(self.portefeuille),
            "demande_exemple": self.demande_exemple,
        }


PROFILS: dict[str, Profil] = {
    "amira": Profil(
        cle="amira",
        nom="Amira",
        resume="26 ans, ingénieure logicielle, risque élevé, horizon de 15 ans ou plus.",
        objectif="Faire croître son capital à long terme.",
        capital=40_000,
        horizon_ans=15,
        budget_perte=0.45,
        plafond_position=0.25,
        plafond_secteur=0.50,
        preferences="Aime l'IA, les technologies émergentes et la crypto, mais veut rester "
                    "diversifiée et ne pas investir seulement en technologie.",
        portefeuille={"QQQ": 35, "NVDA": 15, "SHOP.TO": 10, "XIU.TO": 20, "BTC-USD": 10, "XBB.TO": 10},
        demande_exemple=("ETH-USD", 0.20),
    ),
    "mateo": Profil(
        cle="mateo",
        nom="Mateo",
        resume="41 ans, gestionnaire des opérations, en couple, deux enfants, risque modéré, "
               "horizon de 8 à 12 ans.",
        objectif="Croissance équilibrée du capital à moyen et long terme.",
        capital=150_000,
        horizon_ans=8,
        budget_perte=0.25,
        plafond_position=0.15,
        plafond_secteur=0.40,
        filtre_esg=True,
        secteurs_a_justifier=("Energy",),
        preferences="Accorde une grande importance aux facteurs ESG et veut éviter les "
                    "entreprises impliquées dans des controverses environnementales ou sociales.",
        portefeuille={"ESGV": 30, "XIU.TO": 25, "XBB.TO": 30, "GLD": 5, "MSFT": 10},
        demande_exemple=("ENB.TO", 0.10),
    ),
    "robert": Profil(
        cle="robert",
        nom="Robert",
        resume="59 ans, professionnel de la santé, retraite dans quelques années, risque faible "
               "à modéré, horizon de 3 à 5 ans.",
        objectif="Préserver le capital en gardant un peu de potentiel de croissance.",
        capital=600_000,
        horizon_ans=3,
        budget_perte=0.12,
        plafond_position=0.10,
        plafond_secteur=0.40,
        classes_exclues=("crypto",),
        preferences="Préfère les entreprises établies qu'il comprend ; peu d'intérêt pour la "
                    "crypto ; peut être tenté par une entreprise très médiatisée.",
        portefeuille={"XBB.TO": 35, "ZST.TO": 15, "XIU.TO": 20, "SPY": 10, "RY.TO": 5,
                      "FTS.TO": 5, "JNJ": 5, "PG": 5},
        demande_exemple=("NVDA", 0.20),
    ),
}

# Dictionnaire standardisé des contraintes de personas (conforme Roadmap Épic 1 - Issue 1.3)
PROFILS_DICTS: dict[str, dict] = {cle: p.to_dict() for cle, p in PROFILS.items()}
