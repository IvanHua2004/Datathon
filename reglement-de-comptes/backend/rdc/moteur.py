"""Moteur de calcul déterministe. Aucun modèle de langage ne calcule de chiffre.

Hypothèse commune : portefeuille à poids constants (rééquilibré chaque jour),
rendements en dollars canadiens. Les résultats décrivent le passé observé
(2021-11 à 2026-11) et ne prédisent rien.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

JOURS_PAR_AN = 252


def normaliser(poids: dict[str, float]) -> dict[str, float]:
    total = sum(poids.values())
    if total <= 0:
        raise ValueError("Le portefeuille est vide.")
    return {t: p / total for t, p in poids.items() if p > 0}


def ajouter_position(poids: dict[str, float], ticker: str, taille: float) -> dict[str, float]:
    """Déplace `taille` (0 à 1) du portefeuille vers `ticker`, financé au prorata du reste."""
    if not 0 <= taille <= 1:
        raise ValueError("La taille doit être entre 0 et 1.")
    base = normaliser(poids)
    nouveau = {t: p * (1 - taille) for t, p in base.items()}
    nouveau[ticker] = nouveau.get(ticker, 0.0) + taille
    return normaliser(nouveau)


def rendements_portefeuille(rend: pd.DataFrame, poids: dict[str, float]) -> pd.Series:
    p = normaliser(poids)
    manquants = [t for t in p if t not in rend.columns]
    if manquants:
        raise KeyError(f"Titres absents des données : {manquants}")
    return (rend[list(p)] * pd.Series(p)).sum(axis=1)


def pire_baisse(r: pd.Series) -> dict:
    """Plus forte baisse du sommet au creux, et temps pour revenir au sommet."""
    valeur = (1 + r).cumprod()
    sommets = valeur.cummax()
    baisse = valeur / sommets - 1
    creux = baisse.idxmin()
    sommet = valeur.loc[:creux].idxmax()
    apres = valeur.loc[creux:]
    retour = apres[apres >= valeur.loc[sommet]]
    date_retour = retour.index[0] if len(retour) else None
    fin = date_retour if date_retour is not None else valeur.index[-1]
    return {
        "profondeur": float(baisse.min()),
        "date_sommet": str(sommet.date()),
        "date_creux": str(creux.date()),
        "date_retour": str(date_retour.date()) if date_retour is not None else None,
        "recupere": date_retour is not None,
        # durée totale sous le sommet ; si non récupéré, c'est une durée minimale
        "annees_sous_le_sommet": round((fin - sommet).days / 365.25, 2),
    }


def rendement_periode(r: pd.Series, debut: str, fin: str) -> float:
    tranche = r.loc[debut:fin]
    return float((1 + tranche).prod() - 1)


def volatilite(r: pd.Series) -> float:
    return float(r.std() * np.sqrt(JOURS_PAR_AN))


def contributions_risque(rend: pd.DataFrame, poids: dict[str, float]) -> dict[str, float]:
    """Part de la variance du portefeuille portée par chaque position (somme = 1)."""
    p = normaliser(poids)
    w = pd.Series(p)
    cov = rend[list(p)].cov()
    marginal = cov @ w
    variance = float(w @ marginal)
    return {t: float(w[t] * marginal[t] / variance) for t in p}


def comportement_en_crise(rend: pd.DataFrame, poids_avant: dict[str, float], ticker: str,
                          quantile: float = 0.10) -> dict:
    """Le titre baisse-t-il les mêmes jours que le portefeuille actuel ?

    Jours de crise = les `quantile` pires jours du portefeuille AVANT l'ajout.
    """
    rp = rendements_portefeuille(rend, poids_avant)
    seuil = rp.quantile(quantile)
    crise = rp <= seuil
    rt = rend[ticker]
    return {
        "correlation_jours_calmes": float(rt[~crise].corr(rp[~crise])),
        "correlation_jours_de_crise": float(rt[crise].corr(rp[crise])),
        "nb_jours_de_crise": int(crise.sum()),
        "rendement_moyen_titre_jours_de_crise": float(rt[crise].mean()),
        "rendement_moyen_portefeuille_jours_de_crise": float(rp[crise].mean()),
    }


def concentration(univers: pd.DataFrame, poids: dict[str, float]) -> dict:
    p = pd.Series(normaliser(poids))
    info = univers.loc[p.index]

    def par(colonne: str) -> dict[str, float]:
        s = p.groupby(info[colonne]).sum().sort_values(ascending=False)
        return {k: float(v) for k, v in s.items()}

    return {
        "par_secteur": par("sector"),
        "par_classe_actif": par("asset_class"),
        "par_devise": par("currency"),
        "plus_grosse_position": {"ticker": str(p.idxmax()), "poids": float(p.max())},
    }


def fourchette_pire_baisse_12_mois(r: pd.Series, n: int = 2000, bloc: int = 21,
                                   graine: int = 0) -> dict:
    """Fourchette de la pire baisse sur 12 mois, par rééchantillonnage par blocs.

    Ce n'est PAS une prévision : on recombine des morceaux d'un mois du passé observé
    pour voir à quel point le chiffre dépend de l'ordre des événements. Une seule
    grande crise (2022) est dans l'échantillon ; la fourchette ne peut pas inventer
    des crises qui n'ont pas été observées.
    """
    rng = np.random.default_rng(graine)
    x = r.to_numpy()
    nb_blocs = JOURS_PAR_AN // bloc
    departs = rng.integers(0, len(x) - bloc, size=(n, nb_blocs))
    indices = (departs[:, :, None] + np.arange(bloc)).reshape(n, nb_blocs * bloc)
    valeur = np.cumprod(1 + x[indices], axis=1)
    sommets = np.maximum.accumulate(valeur, axis=1)
    pires = (valeur / sommets - 1).min(axis=1)
    return {
        "mediane": float(np.median(pires)),
        "defavorable_5pct": float(np.quantile(pires, 0.05)),
        "favorable_95pct": float(np.quantile(pires, 0.95)),
        "nb_tirages": n,
        "taille_bloc_jours": bloc,
    }


def resume(rend: pd.DataFrame, univers: pd.DataFrame, poids: dict[str, float]) -> dict:
    r = rendements_portefeuille(rend, poids)
    return {
        "poids": normaliser(poids),
        "pire_baisse": pire_baisse(r),
        "rendement_2022": rendement_periode(r, "2022-01-01", "2022-12-31"),
        "volatilite_annuelle": volatilite(r),
        "fourchette_12_mois": fourchette_pire_baisse_12_mois(r),
        "contributions_risque": contributions_risque(rend, poids),
        "concentration": concentration(univers, poids),
    }


def courbe_taille(rend: pd.DataFrame, poids: dict[str, float], ticker: str,
                  tailles: list[float]) -> list[dict]:
    """Pour chaque taille de position : pire baisse observée et fourchette défavorable."""
    lignes = []
    for taille in tailles:
        p = ajouter_position(poids, ticker, taille)
        r = rendements_portefeuille(rend, p)
        lignes.append({
            "taille": taille,
            "pire_baisse": pire_baisse(r)["profondeur"],
            "defavorable_5pct_12_mois": fourchette_pire_baisse_12_mois(r)["defavorable_5pct"],
            "part_du_risque_du_titre": contributions_risque(rend, p).get(ticker, 0.0),
        })
    return lignes


# -----------------------------------------------------------------------------
# Fonctions déterministes par actif (conforme Roadmap Épic 1 - Issue 1.2)
# -----------------------------------------------------------------------------

def calculer_rendement_annualise(ticker: str, rendements: pd.DataFrame | None = None) -> dict:
    """Calcule le rendement annualisé (CAGR) et cumulé d'un actif.
    
    Retourne un dictionnaire simple lisible par les agents LLM.
    """
    if rendements is None:
        from . import donnees
        rendements = donnees.load_market_data().rendements

    if ticker not in rendements.columns:
        raise KeyError(f"Ticker '{ticker}' absent des données de rendement.")

    r = rendements[ticker]
    cumule = float((1 + r).prod() - 1)
    nb_jours = len(r)
    annees = nb_jours / JOURS_PAR_AN
    cagr = float((1 + cumule) ** (1 / annees) - 1) if annees > 0 and (1 + cumule) > 0 else 0.0

    return {
        "ticker": ticker,
        "rendement_annualise": cagr,
        "rendement_cumule": cumule,
        "nb_jours": nb_jours,
        "debut": str(r.index[0].date()),
        "fin": str(r.index[-1].date()),
    }


def calculer_max_drawdown(ticker: str, annee: int | None = None, rendements: pd.DataFrame | None = None) -> dict:
    """Calcule la pire baisse (maximum drawdown) d'un actif, globale ou pour une année précise (ex: 2022).
    
    Retourne un dictionnaire simple lisible par les agents LLM.
    """
    if rendements is None:
        from . import donnees
        rendements = donnees.load_market_data().rendements

    if ticker not in rendements.columns:
        raise KeyError(f"Ticker '{ticker}' absent des données de rendement.")

    r = rendements[ticker]
    if annee is not None:
        r = r[r.index.year == int(annee)]
        if r.empty:
            raise ValueError(f"Aucune donnée pour le ticker '{ticker}' en l'année {annee}.")

    pb = pire_baisse(r)
    return {
        "ticker": ticker,
        "annee": annee,
        "max_drawdown": pb["profondeur"],
        "date_sommet": pb["date_sommet"],
        "date_creux": pb["date_creux"],
        "date_retour": pb["date_retour"],
        "recupere": pb["recupere"],
        "annees_sous_le_sommet": pb["annees_sous_le_sommet"],
    }


def verifier_volatilite(ticker: str, rendements: pd.DataFrame | None = None) -> dict:
    """Calcule la volatilité annualisée d'un actif et qualifie son niveau de risque.
    
    Retourne un dictionnaire simple lisible par les agents LLM.
    """
    if rendements is None:
        from . import donnees
        rendements = donnees.load_market_data().rendements

    if ticker not in rendements.columns:
        raise KeyError(f"Ticker '{ticker}' absent des données de rendement.")

    r = rendements[ticker]
    vol = volatilite(r)
    if vol > 0.35:
        niveau = "élevé"
    elif vol > 0.15:
        niveau = "modéré"
    else:
        niveau = "faible"

    return {
        "ticker": ticker,
        "volatilite_annuelle": vol,
        "volatilite_quotidienne": float(r.std()),
        "niveau_risque": niveau,
    }
