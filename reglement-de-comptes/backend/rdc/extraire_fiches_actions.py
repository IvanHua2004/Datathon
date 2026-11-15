"""Script d'extraction et de précalcul des fiches d'analyse pour chaque action/actif.

Permet d'extraire et de synthétiser toutes les métriques financières avancées
pour chacun des 31 actifs de l'univers :
- Identité, prix et rendements cumulés / CAGR
- Risque de queue (VaR 95/99%, CVaR, Cornish-Fisher, Skewness, Kurtosis)
- Ratios de performance (Sharpe, Sortino, Calmar)
- Sensibilités de marché et macro (Bêta SPY, Bêta XIU, corrélation taux et devise)
- Régimes de crise historiques (choc 2022, panique bancaire 2023, rallye 2024)
- Dividendes et fractionnements (splits) depuis corporate_actions.csv
- Preuves ESG et décomposition des FNB (look-through)
- Synthèse textuelle et étiquettes sémantiques pour les agents LLM

Les fiches sont sauvegardées en JSON individuel, en CSV récapitulatif,
et synchronisées automatiquement avec la base de données S3.

Utilisation :
    python backend/rdc/extraire_fiches_actions.py [--upload-s3] [--output-dir dossier]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

# Permettre l'exécution directe du script depuis n'importe quel dossier
RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from rdc import analyse_avancee, donnees, moteur, s3_service, temoins


def extraire_fiche_pour_actif(
    ticker: str,
    d: donnees.Donnees,
    macro_df: pd.DataFrame,
    actions_corp_df: pd.DataFrame,
    fx_series: pd.Series,
    preuves_esg_df: pd.DataFrame,
) -> dict:
    """Calcule l'ensemble des métriques avancées pour un titre individuel."""
    univers = d.univers
    if ticker not in univers.index:
        raise KeyError(f"Ticker '{ticker}' introuvable dans l'univers.")

    info_meta = univers.loc[ticker].to_dict()
    r = d.rendements[ticker]
    prix_serie_cad = d.prix_cad[ticker]
    dernier_prix_cad = float(prix_serie_cad.iloc[-1])

    # 1. Rendements temporels
    cumule_total = float((1 + r).prod() - 1)
    nb_jours = len(r)
    annees = nb_jours / analyse_avancee.JOURS_PAR_AN
    cagr = float((1 + cumule_total) ** (1 / annees) - 1) if annees > 0 and (1 + cumule_total) > 0 else 0.0

    rend_1an = float((1 + r.iloc[-252:]).prod() - 1) if len(r) >= 252 else cumule_total
    rend_3ans = float((1 + r.iloc[-252 * 3:]).prod() - 1) if len(r) >= 252 * 3 else cumule_total

    # 2. Maximum Drawdown
    pb = moteur.pire_baisse(r)
    try:
        pb_2022 = moteur.calculer_max_drawdown(ticker, annee=2022, rendements=d.rendements)
        dd_2022 = pb_2022["max_drawdown"]
    except Exception:
        dd_2022 = None

    # 3. Moments d'ordre supérieur et normalité
    moments = analyse_avancee.calculer_moments(r)

    # 4. VaR et Expected Shortfall (CVaR)
    var_95 = analyse_avancee.calculer_var_cvar(r, alpha=0.05)
    var_99 = analyse_avancee.calculer_var_cvar(r, alpha=0.01)

    # 5. Ratios de performance ajustée au risque (taux sans risque ~3.5% moyen)
    ratios = analyse_avancee.calculer_ratios_performance(r, rf_annual=0.035, max_dd=pb["profondeur"])

    # 6. Bêtas de marché et corrélations macro
    sensibilites = analyse_avancee.calculer_sensibilites_marche_et_macro(
        ticker=ticker,
        rendements=d.rendements,
        macro_df=macro_df,
        fx_series=fx_series,
    )

    # 7. Régimes historiques de stress
    regimes = analyse_avancee.analyser_regimes_historiques(r)

    # 8. Dividendes et fractionnements d'actions
    actions_corp = analyse_avancee.analyser_actions_corporatives(
        ticker=ticker,
        actions_df=actions_corp_df,
        prix_actuel=dernier_prix_cad,
    )

    # 9. Preuves et exclusions ESG
    esg_entries = []
    if not preuves_esg_df.empty:
        sub_esg = preuves_esg_df[preuves_esg_df["ticker"] == ticker]
        for row in sub_esg.itertuples():
            esg_entries.append({
                "type": getattr(row, "type", ""),
                "nature": getattr(row, "nature", ""),
                "fait": getattr(row, "fait", ""),
                "source": getattr(row, "source", ""),
                "url": getattr(row, "url", ""),
                "date_document": getattr(row, "date_document", ""),
            })

    # 10. Décomposition FNB (look-through) si applicable
    look_through = analyse_avancee.FNB_COMPOSITIONS.get(ticker, {})

    # 11. Tags sémantiques et synthèse prête pour les agents LLM
    tags, synthese_agent = analyse_avancee.generer_tags_et_synthese_agent(
        ticker=ticker,
        info_univers=info_meta,
        ratios=ratios,
        moments=moments,
        var_dict=var_95,
        sensibilites=sensibilites,
        actions_corp=actions_corp,
    )

    return {
        "ticker": ticker,
        "nom": str(info_meta.get("name", ticker)),
        "classe_actif": str(info_meta.get("asset_class", "")),
        "marche": str(info_meta.get("market", "")),
        "devise_origine": str(info_meta.get("currency", "")),
        "secteur": str(info_meta.get("sector", "")),
        "prix": {
            "dernier_prix_cad": round(dernier_prix_cad, 2),
            "date_dernier_prix": str(prix_serie_cad.index[-1].date()),
            "prix_min_5ans_cad": round(float(prix_serie_cad.min()), 2),
            "prix_max_5ans_cad": round(float(prix_serie_cad.max()), 2),
        },
        "rendements": {
            "cumule_5ans": round(cumule_total, 4),
            "cagr_annualise": round(cagr, 4),
            "rendement_1an": round(rend_1an, 4),
            "rendement_3ans": round(rend_3ans, 4),
            "nb_jours_observes": nb_jours,
            "date_debut": str(r.index[0].date()),
            "date_fin": str(r.index[-1].date()),
        },
        "risque": {
            "volatilite_annuelle": ratios["volatilite_annuelle"],
            "volatilite_baisse_semi_deviation": ratios["volatilite_baisse_sortino"],
            "pire_baisse_globale": pb["profondeur"],
            "pire_baisse_2022": dd_2022,
            "creux_date": pb["date_creux"],
            "sommet_date": pb["date_sommet"],
            "annees_sous_le_sommet": pb["annees_sous_le_sommet"],
            "a_recupere_sommet": pb["recupere"],
            "var_95_quotidienne": var_95["var_quotidienne_historique"],
            "cvar_95_expected_shortfall": var_95["cvar_quotidienne_historique"],
            "var_95_cornish_fisher": var_95["var_quotidienne_cornish_fisher"],
            "var_99_quotidienne": var_99["var_quotidienne_historique"],
            "cvar_99_expected_shortfall": var_99["cvar_quotidienne_historique"],
            "var_95_1mois_estimee": var_95["var_1_mois_estimee"],
        },
        "distribution": moments,
        "ratios_performance": ratios,
        "sensibilites_marche_et_macro": sensibilites,
        "regimes_historiques": regimes,
        "actions_corporatives": actions_corp,
        "esg_preuves": esg_entries,
        "fnb_composition_top_holdings": look_through,
        "tags_semantiques": tags,
        "synthese_agent_llm": synthese_agent,
    }


def extraire_toutes_les_actions(
    dossier_sortie: Path | None = None,
    televerser_s3: bool = True,
) -> dict[str, Any]:
    """Exécute l'extraction complète pour tous les actifs et sauvegarde les résultats."""
    t0 = time.time()
    cible_dossier = dossier_sortie or (donnees.dossier_donnees() / "extracted_actions")
    cible_dossier.mkdir(parents=True, exist_ok=True)

    print(f"[*] Chargement des données de marché...")
    d = donnees.load_market_data()
    macro_df = donnees.charger_macro()
    actions_corp_df = donnees.lire_csv("corporate_actions.csv")
    fx_series = donnees._fx()

    chemin_esg = RACINE / "donnees_externes" / "esg_preuves.csv"
    preuves_esg_df = pd.read_csv(chemin_esg) if chemin_esg.exists() else pd.DataFrame()

    print(f"[*] Extraction des métriques pour {len(d.univers)} actifs...")
    toutes_fiches = {}
    lignes_resume = []

    for ticker in d.univers.index:
        fiche = extraire_fiche_pour_actif(
            ticker=ticker,
            d=d,
            macro_df=macro_df,
            actions_corp_df=actions_corp_df,
            fx_series=fx_series,
            preuves_esg_df=preuves_esg_df,
        )
        toutes_fiches[ticker] = fiche

        # Fichier JSON individuel par action
        fichier_json = cible_dossier / f"{ticker}.json"
        with open(fichier_json, "w", encoding="utf-8") as f:
            json.dump(fiche, f, ensure_ascii=False, indent=2)

        # Ligne récapitulative pour le CSV maître
        lignes_resume.append({
            "ticker": ticker,
            "nom": fiche["nom"],
            "classe_actif": fiche["classe_actif"],
            "secteur": fiche["secteur"],
            "prix_cad": fiche["prix"]["dernier_prix_cad"],
            "cagr_5ans": fiche["rendements"]["cagr_annualise"],
            "rendement_1an": fiche["rendements"]["rendement_1an"],
            "volatilite_annuelle": fiche["risque"]["volatilite_annuelle"],
            "pire_baisse": fiche["risque"]["pire_baisse_globale"],
            "var_95_quotidienne": fiche["risque"]["var_95_quotidienne"],
            "cvar_95_quotidienne": fiche["risque"]["cvar_95_expected_shortfall"],
            "ratio_sharpe": fiche["ratios_performance"]["ratio_sharpe"],
            "ratio_sortino": fiche["ratios_performance"]["ratio_sortino"],
            "ratio_calmar": fiche["ratios_performance"]["ratio_calmar"],
            "beta_spy": fiche["sensibilites_marche_et_macro"].get("beta_spy_cad"),
            "beta_xiu": fiche["sensibilites_marche_et_macro"].get("beta_xiu_canada"),
            "rendement_dividende": fiche["actions_corporatives"]["rendement_dividende_pct"],
            "excess_kurtosis": fiche["distribution"]["excess_kurtosis"],
            "skewness": fiche["distribution"]["skewness"],
            "nb_preuves_esg": len(fiche["esg_preuves"]),
            "tags": " ; ".join(fiche["tags_semantiques"]),
        })

    # Sauvegarde du catalogue global en JSON et CSV
    df_resume = pd.DataFrame(lignes_resume)
    csv_resume = cible_dossier / "actions_summary.csv"
    df_resume.to_csv(csv_resume, index=False, encoding="utf-8")

    json_resume = cible_dossier / "actions_summary.json"
    with open(json_resume, "w", encoding="utf-8") as f:
        json.dump(toutes_fiches, f, ensure_ascii=False, indent=2)

    # Optionnellement en Parquet pour haute performance
    try:
        parquet_resume = cible_dossier / "actions_summary.parquet"
        df_resume.to_parquet(parquet_resume, index=False)
        has_parquet = True
    except Exception:
        has_parquet = False

    duree = time.time() - t0
    print(f"[+] Extraction terminée en {duree:.2f} s. {len(toutes_fiches)} fiches générées dans {cible_dossier}")

    # Synchronisation avec S3 si demandée ou disponible
    s3_statut = {"synchronise": False, "objets_televerses": 0}
    if televerser_s3:
        bucket = s3_service.obtenir_nom_bucket()
        if bucket:
            print(f"[*] Synchronisation des fiches vers AWS S3 (bucket: {bucket})...")
            try:
                nb = s3_service.synchroniser_dossier_s3(
                    dossier_local=cible_dossier,
                    prefixe_s3="extracted_actions",
                )
                s3_statut = {"synchronise": True, "objets_televerses": nb, "bucket": bucket}
                print(f"[+] Succès : {nb} fichiers téléversés sur s3://{bucket}/extracted_actions/")
            except Exception as e:
                s3_statut = {"synchronise": False, "erreur": str(e), "bucket": bucket}
                print(f"[!] Échec de la synchronisation S3 : {e}")
        else:
            print("[i] Aucun bucket S3 configuré. Fiches conservées localement.")

    return {
        "nb_actifs": len(toutes_fiches),
        "dossier_local": str(cible_dossier),
        "duree_secondes": round(duree, 2),
        "s3": s3_statut,
        "format_parquet": has_parquet,
    }


def main():
    parser = argparse.ArgumentParser(description="Extraction et précalcul des fiches d'actifs pour les agents.")
    parser.add_argument("--output-dir", type=str, default=None, help="Dossier de destination local.")
    parser.add_argument("--upload-s3", action="store_true", help="Forcer la synchronisation avec le bucket S3.")
    parser.add_argument("--no-s3", action="store_true", help="Désactiver l'upload S3.")
    parser.add_argument("--ticker", type=str, default=None, help="Extraire un seul ticker spécifique.")
    args = parser.parse_args()

    upload = not args.no_s3 if not args.upload_s3 else True
    dossier = Path(args.output_dir) if args.output_dir else None

    if args.ticker:
        d = donnees.load_market_data()
        macro_df = donnees.charger_macro()
        actions_corp_df = donnees.lire_csv("corporate_actions.csv")
        fx_series = donnees._fx()
        chemin_esg = RACINE / "donnees_externes" / "esg_preuves.csv"
        preuves_esg = pd.read_csv(chemin_esg) if chemin_esg.exists() else pd.DataFrame()

        fiche = extraire_fiche_pour_actif(args.ticker, d, macro_df, actions_corp_df, fx_series, preuves_esg)
        print(json.dumps(fiche, ensure_ascii=False, indent=2))
    else:
        extraire_toutes_les_actions(dossier_sortie=dossier, televerser_s3=upload)


if __name__ == "__main__":
    main()
