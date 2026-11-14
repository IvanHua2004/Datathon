"""Module d'analyse quantitative avancée pour le tribunal Règlement de Comptes.

Enrichit les données brutes avec :
- Métriques de risque de queue : VaR 95% / 99% (historique et Cornish-Fisher), CVaR / Expected Shortfall ;
- Moments d'ordre supérieur : Asymétrie (skewness), Aplatissement (kurtosis), test de Jarque-Bera ;
- Ratios de performance ajustée au risque : Sharpe, Sortino (downside risk), Calmar ;
- Sensibilités macroéconomiques et facteurs de marché : Bêta (SPY, XIU), sensibilité taux BoC / US 10Y, sensibilité FX ;
- Tests de résistance par régimes historiques (choc de taux 2022, panique bancaire 2023, rallye IA 2024) ;
- Analyse des actions corporatives : dividendes, rendement du dividende, fractionnements (splits) ;
- Décomposition par transparence (look-through) des FNB pour détecter la concentration cachée.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

JOURS_PAR_AN = 252

# Décomposition indicative des principaux FNB de l'univers pour le calcul de transparence (look-through)
FNB_COMPOSITIONS: dict[str, dict[str, float]] = {
    "SPY": {
        "MSFT": 0.071, "AAPL": 0.069, "NVDA": 0.062, "AMZN": 0.038,
        "GOOGL": 0.023, "TSLA": 0.018, "JPM": 0.013, "JNJ": 0.011, "XOM": 0.010,
    },
    "QQQ": {
        "AAPL": 0.088, "MSFT": 0.084, "NVDA": 0.079, "AMZN": 0.052,
        "GOOGL": 0.048, "TSLA": 0.028,
    },
    "XIU.TO": {
        "RY.TO": 0.085, "TD.TO": 0.068, "ENB.TO": 0.052, "CNQ.TO": 0.044,
        "CNR.TO": 0.039, "SHOP.TO": 0.038, "CSU.TO": 0.029, "ATD.TO": 0.024,
    },
    "ESGV": {
        "MSFT": 0.075, "AAPL": 0.072, "NVDA": 0.065, "AMZN": 0.040,
        "GOOGL": 0.025, "TSLA": 0.019, "JPM": 0.014,
        # Filtre ESG exclut formellement XOM, CNQ, etc.
    },
}


def calculer_moments(r: pd.Series) -> dict[str, Any]:
    """Calcule l'asymétrie (skewness), l'aplatissement (kurtosis) et la normalité."""
    serie = r.dropna().to_numpy()
    if len(serie) < 30:
        return {"skewness": 0.0, "kurtosis": 0.0, "est_normale": True, "p_valeur_jb": 1.0}

    skew = float(stats.skew(serie))
    # kurtosis de Fisher (excès par rapport à la normale 3.0)
    kurt = float(stats.kurtosis(serie, fisher=True))
    stat_jb, p_val_jb = stats.jarque_bera(serie)

    description = []
    if abs(skew) > 0.5:
        description.append("Asymétrie prononcée" if skew > 0 else "Risque de queue négative (chutes asymétriques)")
    if kurt > 1.5:
        description.append("Queues épaisses (leptokurtique : chocs extrêmes plus fréquents qu'une loi normale)")
    elif kurt < -0.5:
        description.append("Queues légères (distribution platykurtique)")

    return {
        "skewness": round(skew, 3),
        "excess_kurtosis": round(kurt, 3),
        "statistique_jb": round(float(stat_jb), 2),
        "p_valeur_jb": float(p_val_jb),
        "est_normale": bool(p_val_jb > 0.05),
        "diagnostic": " ; ".join(description) if description else "Distribution proche d'une loi normale",
    }


def calculer_var_cvar(r: pd.Series, alpha: float = 0.05) -> dict[str, Any]:
    """Calcule la Value at Risk (VaR) et la Conditional VaR (Expected Shortfall / CVaR).

    Paramètres :
        r : série de rendements simples.
        alpha : seuil de risque (0.05 = niveau de confiance 95%).
    """
    serie = r.dropna().to_numpy()
    if len(serie) < 20:
        return {"var_historique": 0.0, "cvar_historique": 0.0, "var_cornish_fisher": 0.0}

    # 1. VaR Historique quotidienne (valeur positive représentant une perte)
    q_alpha = np.quantile(serie, alpha)
    var_hist = float(-q_alpha)

    # 2. CVaR / Expected Shortfall quotidienne : moyenne des pertes pires que la VaR
    pertes_au_dela = serie[serie <= q_alpha]
    cvar_hist = float(-pertes_au_dela.mean()) if len(pertes_au_dela) > 0 else var_hist

    # 3. VaR Cornish-Fisher (ajustée pour l'asymétrie et les queues épaisses)
    mu = float(np.mean(serie))
    sigma = float(np.std(serie))
    s = float(stats.skew(serie))
    k = float(stats.kurtosis(serie, fisher=True))
    z = stats.norm.ppf(alpha)  # ~ -1.645 pour alpha=0.05

    z_cf = (
        z
        + (z**2 - 1) * s / 6.0
        + (z**3 - 3 * z) * k / 24.0
        - (2 * z**3 - 5 * z) * (s**2) / 36.0
    )
    var_cf = float(-(mu + z_cf * sigma))

    # Transposition sur 21 jours ouvrables (horizon 1 mois) : règle de la racine carrée
    var_1mois = var_hist * math.sqrt(21)
    cvar_1mois = cvar_hist * math.sqrt(21)

    return {
        "seuil_confiance": f"{int((1 - alpha) * 100)} %",
        "var_quotidienne_historique": round(var_hist, 4),
        "cvar_quotidienne_historique": round(cvar_hist, 4),
        "var_quotidienne_cornish_fisher": round(var_cf, 4),
        "var_1_mois_estimee": round(var_1mois, 4),
        "cvar_1_mois_estimee": round(cvar_1mois, 4),
    }


def calculer_volatilite_baissee(r: pd.Series, seuil: float = 0.0) -> float:
    """Écart-type semi-déviation (rendements inférieurs au seuil uniquement), annualisé."""
    neg = r[r < seuil]
    if len(neg) == 0:
        return 0.0
    semi_variance = (neg ** 2).sum() / len(r)
    return float(np.sqrt(semi_variance * JOURS_PAR_AN))


def calculer_ratios_performance(r: pd.Series, rf_annual: float = 0.035, max_dd: float | None = None) -> dict[str, Any]:
    """Calcule les ratios de performance ajustée au risque (Sharpe, Sortino, Calmar)."""
    cumule = float((1 + r).prod() - 1)
    annees = len(r) / JOURS_PAR_AN
    cagr = float((1 + cumule) ** (1 / annees) - 1) if annees > 0 and (1 + cumule) > 0 else 0.0

    vol_ann = float(r.std() * np.sqrt(JOURS_PAR_AN))
    downside_vol = calculer_volatilite_baissee(r, seuil=rf_annual / JOURS_PAR_AN)

    sharpe = (cagr - rf_annual) / vol_ann if vol_ann > 0 else 0.0
    sortino = (cagr - rf_annual) / downside_vol if downside_vol > 0 else 0.0

    calmar = None
    if max_dd is not None and abs(max_dd) > 0:
        calmar = round(cagr / abs(max_dd), 2)

    return {
        "cagr": round(cagr, 4),
        "volatilite_annuelle": round(vol_ann, 4),
        "volatilite_baisse_sortino": round(downside_vol, 4),
        "taux_sans_risque_utilise": round(rf_annual, 4),
        "ratio_sharpe": round(sharpe, 2),
        "ratio_sortino": round(sortino, 2),
        "ratio_calmar": calmar,
    }


def calculer_sensibilites_marche_et_macro(
    ticker: str,
    rendements: pd.DataFrame,
    macro_df: pd.DataFrame,
    fx_series: pd.Series,
) -> dict[str, Any]:
    """Mesure les bêtas de marché (SPY, XIU) et les corrélations aux variables macro."""
    if ticker not in rendements.columns:
        return {}

    rt = rendements[ticker]
    resultats: dict[str, Any] = {}

    # 1. Bêtas par rapport aux marchés de référence (SPY en CAD et XIU.TO)
    for ref, nom in [("SPY", "beta_spy_cad"), ("XIU.TO", "beta_xiu_canada")]:
        if ref in rendements.columns and ref != ticker:
            rx = rendements[ref]
            var_x = float(rx.var())
            if var_x > 0:
                cov = float(rt.cov(rx))
                beta = cov / var_x
                # Alpha annualisé (CAPM)
                cagr_t = float((1 + rt).prod() ** (JOURS_PAR_AN / len(rt)) - 1)
                cagr_x = float((1 + rx).prod() ** (JOURS_PAR_AN / len(rx)) - 1)
                alpha = cagr_t - (0.035 + beta * (cagr_x - 0.035))
                resultats[nom] = round(beta, 2)
                resultats[f"alpha_annuel_vs_{ref.lower()}"] = round(alpha, 4)
                resultats[f"correlation_vs_{ref.lower()}"] = round(float(rt.corr(rx)), 2)

    # 2. Corrélation avec les variations quotidiennes du taux de change USD/CAD
    r_fx = fx_series.pct_change().reindex(rt.index).dropna()
    if len(r_fx) > 0:
        corr_fx = float(rt.reindex(r_fx.index).corr(r_fx))
        resultats["correlation_variation_usdcad"] = round(corr_fx, 2)

    # 3. Corrélation avec les taux d'intérêt (Canada 10 ans et US 10 ans)
    # On calcule la corrélation avec la variation des taux sur les dates communes
    for code, nom in [
        ("BD.CDN.10YR.DQ.YLD", "correlation_taux_10y_canada"),
        ("DGS10", "correlation_taux_10y_us"),
        ("V39079", "correlation_taux_directeur_boc"),
    ]:
        sub = macro_df[macro_df["series_id"] == code].sort_values("date")
        if not sub.empty:
            serie_taux = sub.set_index("date")["value"].reindex(rt.index).ffill()
            delta_taux = serie_taux.diff().dropna()
            corr_taux = float(rt.reindex(delta_taux.index).corr(delta_taux))
            resultats[nom] = round(corr_taux, 2)

    return resultats


def analyser_regimes_historiques(r: pd.Series) -> dict[str, Any]:
    """Évalue la performance et la pire baisse pendant les périodes historiques de stress."""
    regimes = {
        "choc_taux_et_inflation_2022": ("2022-01-03", "2022-10-14"),
        "crise_bancaire_us_2023": ("2023-03-01", "2023-05-01"),
        "expansion_technologique_ia_2024": ("2024-01-02", "2024-11-01"),
    }
    bilan = {}
    for nom_regime, (debut, fin) in regimes.items():
        tranche = r.loc[debut:fin]
        if len(tranche) > 10:
            rend_total = float((1 + tranche).prod() - 1)
            # max drawdown sur la tranche
            val = (1 + tranche).cumprod()
            dd = float((val / val.cummax() - 1).min())
            bilan[nom_regime] = {
                "periode": f"{debut} au {fin}",
                "rendement_cumule": round(rend_total, 4),
                "pire_baisse_pendant_regime": round(dd, 4),
            }
    return bilan


def analyser_actions_corporatives(
    ticker: str,
    actions_df: pd.DataFrame,
    prix_actuel: float,
) -> dict[str, Any]:
    """Extrait les dividendes et fractionnements d'actions depuis corporate_actions.csv."""
    if actions_df.empty or "ticker" not in actions_df.columns:
        return {"dividende_annuel_estime": 0.0, "rendement_dividende_pct": 0.0, "nb_splits": 0}

    sous_actions = actions_df[actions_df["ticker"] == ticker]
    if sous_actions.empty:
        return {
            "dividende_annuel_estime": 0.0,
            "rendement_dividende_pct": 0.0,
            "nb_paiements_dividendes": 0,
            "frequence_dividende": "Aucun dividende",
            "splits": [],
        }

    divs = sous_actions[sous_actions["action"] == "dividend"].copy()
    splits = sous_actions[sous_actions["action"] == "split"].copy()

    # Calcul du dividende annuel moyen récent (12 derniers mois de dividendes)
    rendement_div = 0.0
    div_annuel = 0.0
    freq = "Aucun"
    if not divs.empty:
        divs["ex_date"] = pd.to_datetime(divs["ex_date"])
        divs = divs.sort_values("ex_date")
        nb_divs = len(divs)
        # Dividendes des 12 derniers mois observés
        derniere_date = divs["ex_date"].max()
        un_an_avant = derniere_date - pd.Timedelta(days=365)
        divs_12m = divs[divs["ex_date"] >= un_an_avant]
        div_annuel = float(divs_12m["value"].sum()) if not divs_12m.empty else float(divs["value"].iloc[-4:].sum())
        if prix_actuel > 0:
            rendement_div = float(div_annuel / prix_actuel)

        if nb_divs >= 15:
            freq = "Trimestriel" if nb_divs < 30 else "Mensuel"
        elif nb_divs >= 4:
            freq = "Trimestriel"
        elif nb_divs >= 1:
            freq = "Annuel"

    splits_list = []
    if not splits.empty:
        for row in splits.itertuples():
            splits_list.append({"date": str(row.ex_date), "ratio": float(row.value)})

    return {
        "dividende_annuel_estime": round(div_annuel, 3),
        "rendement_dividende_pct": round(rendement_div, 4),
        "nb_paiements_total_5ans": len(divs),
        "frequence_dividende": freq,
        "derniere_date_ex": str(divs["ex_date"].max().date()) if not divs.empty else None,
        "splits": splits_list,
        "nb_splits": len(splits_list),
    }


def generer_tags_et_synthese_agent(
    ticker: str,
    info_univers: dict[str, Any],
    ratios: dict[str, Any],
    moments: dict[str, Any],
    var_dict: dict[str, Any],
    sensibilites: dict[str, Any],
    actions_corp: dict[str, Any],
) -> tuple[list[str], str]:
    """Génère des étiquettes sémantiques et un paragraphe de synthèse prêt à l'emploi pour les LLMs."""
    tags = []
    classe = info_univers.get("asset_class", "")
    secteur = info_univers.get("sector", "")

    # Tags de classe et secteur
    if classe == "crypto":
        tags.append("Cryptoactif")
    elif classe.startswith("etf"):
        tags.append("FNB Indiciel")
    else:
        tags.append("Action Individuelle")

    if secteur:
        tags.append(secteur)

    # Tags de risque et volatilité
    vol = ratios.get("volatilite_annuelle", 0.0)
    if vol > 0.45:
        tags.append("Volatilité Extrême")
    elif vol > 0.25:
        tags.append("Volatilité Élevée")
    elif vol < 0.12:
        tags.append("Défensif / Faible Volatilité")

    # Tags de distribution et queue
    if moments.get("excess_kurtosis", 0.0) > 1.5:
        tags.append("Queues Épaisses (Fat Tails)")
    if moments.get("skewness", 0.0) < -0.4:
        tags.append("Asymétrie Baissière")

    # Tags de rendement dividende
    yield_div = actions_corp.get("rendement_dividende_pct", 0.0)
    if yield_div >= 0.04:
        tags.append("Fort Dividende (>4%)")
    elif yield_div > 0.015:
        tags.append("Dividende Régulier")
    else:
        tags.append("Sans Dividende / Réinvestissement")

    # Tags macro et bêtas
    beta_spy = sensibilites.get("beta_spy_cad")
    if beta_spy is not None:
        if beta_spy > 1.3:
            tags.append("Haut Bêta (>1.3)")
        elif beta_spy < 0.7:
            tags.append("Bêta Défensif (<0.7)")

    corr_taux = sensibilites.get("correlation_taux_10y_us")
    if corr_taux is not None and corr_taux < -0.25:
        tags.append("Vulnérable aux Taux d'Intérêt")

    # Synthèse textuelle pour agents
    nom = info_univers.get("name", ticker)
    cagr = ratios.get("cagr", 0.0)
    sharpe = ratios.get("ratio_sharpe", 0.0)
    var95 = var_dict.get("var_quotidienne_historique", 0.0)

    synthese = (
        f"{nom} ({ticker}) est un actif de type {classe} ({secteur}). Sur la période observée de 5 ans, "
        f"il affiche un rendement annualisé de {cagr:.1%} pour une volatilité de {vol:.1%} (ratio de Sharpe de {sharpe}). "
        f"Sa VaR quotidienne à 95% est de {var95:.1%}. Son profil se caractérise par : {', '.join(tags)}."
    )

    return tags, synthese
