"""L'archiviste : un agent distinct du greffier, qui récite les chiffres du jeu de données.

Règles de l'agent :
- seulement des faits calculés sur les CSV des organisateurs (prix ajustés, convertis en CAD);
- aucune opinion, aucune recommandation, aucune prévision;
- pas de comparaison : chaque titre a sa propre fiche, sans classement ni « meilleur que ».
  Pour juger une décision, l'investisseur passe par le tribunal.

Tout est calculé par du code, sans modèle de langage : un chiffre affiché ne peut pas être inventé.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

import numpy as np

from . import donnees
from .format import nombre, pct
from .moteur import JOURS_PAR_AN, pire_baisse

# Une question de chiffres, pas une décision : « les stats de NVDA », « combien a fait Tesla »…
DEMANDE_DE_CHIFFRES = (
    r"\bstats?\b", r"statisti", r"\bdonnees\b", r"\bchiffres?\b", r"performance", r"\brendements?\b",
    r"volatilit", r"historique", r"\binfos?\b", r"information", r"\bfiche\b", r"\bprix\b",
    r"combien (?:a|ont) (?:rapporte|fait|perdu|gagne)", r"\bc'?est quoi\b", r"parle[- ]moi",
    r"presente[- ]moi", r"\bmontre[- ]moi\b", r"pire baisse", r"\bperformances?\b",
)
# Demande de la liste des actifs : « quelles compagnies ? », « qu'est-ce que je peux choisir ? »
DEMANDE_DE_CATALOGUE = (
    r"\bquel(?:le)?s? (?:sont les )?(?:compagnies|entreprises|titres|actifs|actions|choix|options|placements|fnb|etf)",
    r"\bliste\b", r"\bcatalogue\b", r"qu'?est-ce que je peux (?:choisir|acheter|investir|placer)",
    r"\btous les (?:titres|actifs|choix)", r"\btoutes les (?:compagnies|entreprises|actions|options)",
    r"(?:compagnies|entreprises|actifs|titres|actions|options) (?:disponibles|possibles|connus?)",
    r"\bque connais-tu\b", r"\bquoi choisir\b",
)
# Demande de comparaison : « NVDA ou l'or ? », « compare Apple et Shopify », « tech vs énergie »
DEMANDE_DE_COMPARAISON = (
    r"compar", r"\bvs\.?\b", r"\bversus\b", r"\bcontre\b", r"difference", r"\bou\b",
    r"\blequel\b", r"\blaquelle\b", r"\bentre\b",
)
MAX_FICHES = 2

GROUPES = [
    ("Actions canadiennes", lambda i: i["asset_class"] == "equity" and i["market"] == "TSX"),
    ("Actions américaines", lambda i: i["asset_class"] == "equity" and i["market"] != "TSX"),
    ("FNB d'actions (paniers)", lambda i: i["asset_class"] == "etf_equity"),
    ("Obligations", lambda i: i["asset_class"] == "etf_bond"),
    ("Or", lambda i: i["asset_class"] == "etf_commodity"),
    ("Cryptoactifs", lambda i: i["asset_class"] == "crypto"),
]

CLASSES = {
    "equity": "Action",
    "etf_equity": "FNB d'actions",
    "etf_bond": "FNB d'obligations",
    "etf_commodity": "FNB de matière première",
    "crypto": "Cryptoactif",
}

LIMITES = ("Chiffres du passé, en dollars canadiens, sur la période du jeu de données. "
           "Ils ne prédisent pas l'avenir et ne sont pas une recommandation.")


@dataclass
class Fait:
    libelle: str
    valeur: str
    aide: str = ""


@dataclass
class Fiche:
    ticker: str
    nomTitre: str
    classe: str
    secteur: str
    marche: str
    devise: str
    periode: dict
    faits: list[Fait]
    source: str
    limites: str = LIMITES

    def en_json(self) -> dict:
        return asdict(self)


def _signe(x: float) -> str:
    return ("+" if x > 0 else "") + pct(x)


def demande_des_chiffres(texte_norm: str) -> bool:
    return any(re.search(m, texte_norm) for m in DEMANDE_DE_CHIFFRES)


def demande_le_catalogue(texte_norm: str) -> bool:
    return any(re.search(m, texte_norm) for m in DEMANDE_DE_CATALOGUE)


def demande_une_comparaison(texte_norm: str) -> bool:
    return any(re.search(m, texte_norm) for m in DEMANDE_DE_COMPARAISON)


def _titre(ticker: str, portefeuille: set[str], classes_exclues: set[str]) -> dict:
    info = donnees.charger().univers.loc[ticker]
    return {
        "ticker": ticker,
        "nomTitre": str(info["name"]),
        "secteur": str(info["sector"]),
        "dansPortefeuille": ticker in portefeuille,
        "exclu": str(info["asset_class"]) in classes_exclues,
    }


def catalogue(portefeuille: set[str] = frozenset(), classes_exclues: set[str] = frozenset(),
              seulement: list[str] | None = None, theme: str | None = None) -> dict:
    """Les actifs du jeu de données, groupés par domaine (ou seulement ceux d'un thème)."""
    univers = donnees.charger().univers
    if seulement:
        groupes = [{"nom": (theme or "Titres").capitalize(), "titres": [_titre(t, portefeuille, classes_exclues) for t in seulement]}]
        message = (f"Pour {theme}, le jeu de données contient {len(seulement)} titre"
                   f"{'s' if len(seulement) > 1 else ''}. Cliquez sur un titre pour voir ses chiffres.")
    else:
        groupes = []
        for nom, filtre in GROUPES:
            titres = [_titre(t, portefeuille, classes_exclues) for t in univers.index if filtre(univers.loc[t])]
            if titres:
                groupes.append({"nom": nom, "titres": titres})
        message = (f"Le tribunal connaît {len(univers)} actifs, tous avec des prix quotidiens du "
                   f"{_date(donnees.charger().debut)} au {_date(donnees.charger().fin)}. "
                   "Cliquez sur un titre pour voir ses chiffres, ou demandez une comparaison de deux titres.")
    return {"agent": "archiviste", "message": message, "groupes": groupes}


def comparer(a: str, b: str) -> dict:
    """Deux fiches alignées ligne par ligne. Aucun gagnant : seulement les faits."""
    return {
        "agent": "archiviste",
        "message": ("Voici les mêmes chiffres des deux côtés, sur la même période et en dollars "
                    "canadiens. Je ne dis pas lequel est meilleur : la réponse dépend de votre profil, "
                    "et c'est au tribunal d'en juger."),
        "fiches": [fiche(a).en_json(), fiche(b).en_json()],
    }


def option_moyenne(theme: str, n: int) -> dict:
    return {"ticker": PREFIXE_MOYENNE + theme, "nomTitre": "Moyenne du domaine",
            "secteur": f"panier à parts égales de {n} titres", "dansPortefeuille": False, "exclu": False}


def selection(groupes: list[dict], un_par_groupe: bool) -> dict:
    """Trop vague ou trop de titres : l'archiviste fait choisir exactement deux titres."""
    message = ("Je compare deux titres à la fois. Choisissez un titre dans chaque domaine, puis « Comparer »."
               if un_par_groupe else
               "Je compare deux titres à la fois. Lesquels voulez-vous voir côte à côte ?")
    return {"agent": "archiviste", "message": message, "groupes": groupes,
            "selection": "un_par_groupe" if un_par_groupe else "deux"}


def _date(iso: str) -> str:
    a, m, j = iso.split("-")
    return f"{j}/{m}/{a}"


def _faits(r, valeurs, unite: str) -> list[Fait]:
    """Les 10 chiffres d'une série de rendements quotidiens (un titre ou un panier)."""
    annees = len(r) / JOURS_PAR_AN
    total = float((1 + r).prod() - 1)
    annualise = float((1 + total) ** (1 / annees) - 1)
    vol = float(r.std() * np.sqrt(JOURS_PAR_AN))
    pb = pire_baisse(r)
    par_annee = (1 + r).groupby(r.index.year).prod() - 1
    completes = par_annee.loc[[a for a in par_annee.index if (r.index.year == a).sum() > 200]]
    meilleure, pire = int(completes.idxmax()), int(completes.idxmin())
    recuperation = (f"revenu au sommet le {_date(pb['date_retour'])}" if pb["recupere"]
                    else "pas revenu au sommet à la fin des données")
    return [
        Fait("Valeur au début", f"{nombre(float(valeurs.iloc[0]))}{unite}", _date(str(valeurs.index[0].date()))),
        Fait("Valeur à la fin", f"{nombre(float(valeurs.iloc[-1]))}{unite}", _date(str(valeurs.index[-1].date()))),
        Fait("Variation sur la période", _signe(total), f"sur {nombre(annees, 1)} ans"),
        Fait("Variation moyenne par an", _signe(annualise), "rendement annualisé"),
        Fait("Volatilité annuelle", pct(vol), "ampleur habituelle des variations"),
        Fait("Pire baisse", pct(pb["profondeur"]),
             f"du {_date(pb['date_sommet'])} au {_date(pb['date_creux'])}, {recuperation}"),
        Fait("Meilleure année", _signe(float(completes.loc[meilleure])), f"en {meilleure}"),
        Fait("Pire année", _signe(float(completes.loc[pire])), f"en {pire}"),
        Fait("Meilleure journée", _signe(float(r.max())), _date(str(r.idxmax().date()))),
        Fait("Pire journée", pct(float(r.min())), _date(str(r.idxmin().date()))),
    ]


def fiche(ticker: str) -> Fiche:
    if ticker.startswith(PREFIXE_MOYENNE):
        return fiche_moyenne(ticker[len(PREFIXE_MOYENNE):])
    d = donnees.charger()
    info = d.univers.loc[ticker]
    r = d.rendements[ticker]
    prix = d.prix_cad[ticker].loc[r.index[0]:]
    return Fiche(
        ticker=ticker,
        nomTitre=str(info["name"]),
        classe=CLASSES.get(str(info["asset_class"]), str(info["asset_class"])),
        secteur=str(info["sector"]),
        marche=str(info["market"]),
        devise=str(info["currency"]),
        periode={"debut": d.debut, "fin": d.fin},
        faits=_faits(r, prix, " $ CA"),
        source=d.source(),
    )


# « La moyenne d'un domaine » : un panier à parts égales des titres du domaine, rééquilibré chaque jour.
PREFIXE_MOYENNE = "MOY:"


def fiche_moyenne(theme: str) -> Fiche:
    from .questions import titres_du_theme

    d = donnees.charger()
    tickers = [t for t in titres_du_theme(theme) if t in d.rendements.columns]
    if not tickers:
        raise KeyError(theme)
    r = d.rendements[tickers].mean(axis=1)
    import pandas as pd
    indice = pd.concat([pd.Series([100.0], index=[d.prix_cad.index[0]]), 100 * (1 + r).cumprod()])
    return Fiche(
        ticker=PREFIXE_MOYENNE + theme,
        nomTitre=f"Moyenne : {theme} ({len(tickers)} titres)",
        classe="Panier à parts égales",
        secteur=", ".join(tickers),
        marche="calcul de l'archiviste",
        devise="CAD",
        periode={"debut": d.debut, "fin": d.fin},
        faits=_faits(r, indice, " (indice, départ 100)"),
        source=d.source(),
        limites=LIMITES + " Moyenne à parts égales des titres du domaine, rééquilibrée chaque jour : "
                          "ce n'est pas un produit qu'on peut acheter tel quel.",
    )


def repondre(ticker: str) -> dict:
    """Réponse de l'archiviste sur un titre : sa fiche, sans interprétation."""
    return {"agent": "archiviste",
            "message": "Voici ce que disent les données sur ce titre. Je rapporte les chiffres, sans les interpréter.",
            "fiches": [fiche(ticker).en_json()]}
