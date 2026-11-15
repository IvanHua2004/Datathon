"""Tests des modules d'analyse quantitative avancée et du store d'actions."""
import pytest
import pandas as pd
import numpy as np

from rdc import analyse_avancee, actions_store, s3_service, donnees


def test_moments_et_normalite():
    # Série normale
    rng = np.random.default_rng(42)
    norm = pd.Series(rng.normal(0, 0.01, size=1000))
    res_norm = analyse_avancee.calculer_moments(norm)
    assert abs(res_norm["skewness"]) < 0.2
    assert abs(res_norm["excess_kurtosis"]) < 0.4

    # Série avec asymétrie et queues épaisses
    crash = pd.Series(np.concatenate([rng.normal(0.001, 0.01, size=950), rng.normal(-0.08, 0.02, size=50)]))
    res_crash = analyse_avancee.calculer_moments(crash)
    assert res_crash["skewness"] < -0.5
    assert res_crash["excess_kurtosis"] > 1.0
    assert not res_crash["est_normale"]


def test_var_et_cvar():
    rng = np.random.default_rng(42)
    rend = pd.Series(rng.normal(0.0005, 0.015, size=1000))
    metrics = analyse_avancee.calculer_var_cvar(rend, alpha=0.05)
    # Pour une loi normale N(0, 0.015), VaR 95% est ~ 1.645 * 0.015 = 0.0247
    assert 0.015 < metrics["var_quotidienne_historique"] < 0.035
    # CVaR doit être strictement plus sévère que VaR
    assert metrics["cvar_quotidienne_historique"] > metrics["var_quotidienne_historique"]


def test_ratios_performance():
    rend = pd.Series([0.01, -0.005, 0.008, 0.002, -0.001] * 100)
    ratios = analyse_avancee.calculer_ratios_performance(rend, rf_annual=0.035, max_dd=-0.15)
    assert ratios["volatilite_annuelle"] > 0
    assert ratios["volatilite_baisse_sortino"] > 0
    assert "ratio_sharpe" in ratios
    assert "ratio_sortino" in ratios
    assert ratios["ratio_calmar"] is not None


def test_actions_store_obtenir_fiche():
    fiche_nvda = actions_store.obtenir_fiche_action("NVDA")
    assert fiche_nvda["ticker"] == "NVDA"
    assert fiche_nvda["nom"] == "NVIDIA"
    assert "cagr_annualise" in fiche_nvda["rendements"]
    assert "var_95_quotidienne" in fiche_nvda["risque"]
    assert "ratio_sharpe" in fiche_nvda["ratios_performance"]
    assert len(fiche_nvda["tags_semantiques"]) > 0
    assert len(fiche_nvda["synthese_agent_llm"]) > 0


def test_brief_agent_formate():
    brief = actions_store.formater_brief_pour_agent("AAPL")
    assert "Apple (AAPL)" in brief
    assert "CAGR" in brief
    assert "VaR 95%" in brief
    assert "Bêta" in brief
