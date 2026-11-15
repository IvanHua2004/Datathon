"""Store d'accès rapide aux fiches d'actifs pour les agents du tribunal.

Fournit un accès instantané O(1) aux données précalculées de chaque action/titre,
en mémoire avec repli sur le disque local ou le bucket S3 AWS.

Évite aux agents LLM et au moteur de recalculer les 1 305 séances de cotations
à chaque déposition ou plaidoirie.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from . import donnees, s3_service

RACINE = Path(__file__).resolve().parent.parent


def dossier_extractions() -> Path:
    """Emplacement local des fiches précalculées."""
    return donnees.dossier_donnees() / "extracted_actions"


@lru_cache(maxsize=64)
def obtenir_fiche_action(ticker: str) -> dict[str, Any]:
    """Retourne la fiche complète précalculée d'une action/actif.

    Priorité de recherche :
    1. Mémoire vive (cache LRU)
    2. Fichier local JSON (data/extracted_actions/{ticker}.json)
    3. Bucket S3 AWS (extracted_actions/{ticker}.json)
    4. Calcul à la volée en dernier recours si la fiche n'existe pas encore.
    """
    ticker = ticker.strip()
    dossier = dossier_extractions()
    fichier_local = dossier / f"{ticker}.json"

    # 1. Vérification fichier local
    if fichier_local.exists():
        try:
            with open(fichier_local, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # 2. Vérification S3 AWS
    bucket = s3_service.obtenir_nom_bucket()
    if bucket:
        cle_s3 = f"extracted_actions/{ticker}.json"
        data_s3 = s3_service.lire_json_s3(cle_s3, bucket=bucket)
        if data_s3:
            # Mettre en cache local pour la prochaine fois
            try:
                dossier.mkdir(parents=True, exist_ok=True)
                with open(fichier_local, "w", encoding="utf-8") as f:
                    json.dump(data_s3, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
            return data_s3

    # 3. Calcul à la volée si inexistant
    from . import extraire_fiches_actions
    d = donnees.load_market_data()
    macro_df = donnees.charger_macro()
    actions_corp_df = donnees.lire_csv("corporate_actions.csv")
    fx_series = donnees._fx()
    chemin_esg = RACINE / "donnees_externes" / "esg_preuves.csv"
    preuves_esg = pd.read_csv(chemin_esg) if chemin_esg.exists() else pd.DataFrame()

    fiche = extraire_fiches_actions.extraire_fiche_pour_actif(
        ticker=ticker,
        d=d,
        macro_df=macro_df,
        actions_corp_df=actions_corp_df,
        fx_series=fx_series,
        preuves_esg_df=preuves_esg,
    )

    # Sauvegarde locale
    try:
        dossier.mkdir(parents=True, exist_ok=True)
        with open(fichier_local, "w", encoding="utf-8") as f:
            json.dump(fiche, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return fiche


@lru_cache(maxsize=1)
def obtenir_resume_catalogue() -> pd.DataFrame:
    """Retourne la table récapitulative de tous les actifs de l'univers."""
    fichier_csv = dossier_extractions() / "actions_summary.csv"
    if fichier_csv.exists():
        return pd.read_csv(fichier_csv)

    # Si absent, on génère l'ensemble
    from . import extraire_fiches_actions
    extraire_fiches_actions.extraire_toutes_les_actions(televerser_s3=False)
    if fichier_csv.exists():
        return pd.read_csv(fichier_csv)
    return pd.DataFrame()


def rechercher_actions_par_tags(tag: str) -> list[dict[str, Any]]:
    """Trouve tous les actifs associés à un tag sémantique (ex: 'Volatilité Extrême', 'Fort Dividende')."""
    df = obtenir_resume_catalogue()
    if df.empty or "tags" not in df.columns:
        return []
    masque = df["tags"].str.contains(tag, case=False, na=False)
    return df[masque].to_dict(orient="records")


def formater_brief_pour_agent(ticker: str) -> str:
    """Produit un bloc de texte condensé directement injectable dans les prompts d'agents LLM."""
    fiche = obtenir_fiche_action(ticker)
    nom = fiche["nom"]
    secteur = fiche["secteur"]
    cagr = fiche["rendements"]["cagr_annualise"]
    vol = fiche["risque"]["volatilite_annuelle"]
    max_dd = fiche["risque"]["pire_baisse_globale"]
    var95 = fiche["risque"]["var_95_quotidienne"]
    cvar95 = fiche["risque"]["cvar_95_expected_shortfall"]
    sharpe = fiche["ratios_performance"]["ratio_sharpe"]
    sortino = fiche["ratios_performance"]["ratio_sortino"]
    beta_spy = fiche["sensibilites_marche_et_macro"].get("beta_spy_cad", "N/A")
    tags = ", ".join(fiche["tags_semantiques"])
    div_pct = fiche["actions_corporatives"]["rendement_dividende_pct"]

    return (
        f"FICHE FACTUELLE EXTRAITE : {nom} ({ticker})\n"
        f"- Secteur & Classe : {secteur} | {fiche['classe_actif']} ({fiche['devise_origine']})\n"
        f"- Rendement annualisé (CAGR 5 ans) : {cagr:.1%} | Ratio de Sharpe : {sharpe} | Ratio de Sortino : {sortino}\n"
        f"- Volatilité annuelle : {vol:.1%} | Pire baisse (Max Drawdown) : {max_dd:.1%}\n"
        f"- Risque de queue : VaR 95% = {var95:.1%}/jour | CVaR (Expected Shortfall 95%) = {cvar95:.1%}/jour\n"
        f"- Bêta vs marché US (SPY CAD) : {beta_spy} | Rendement dividende estimé : {div_pct:.1%}\n"
        f"- Profil et étiquettes : {tags}\n"
        f"- Synthèse : {fiche['synthese_agent_llm']}"
    )
