"""Tests unitaires du module rdc.duel : confrontation de deux titres devant le tribunal."""
from rdc import duel, profils


def test_decider_regle_1_gravite():
    # Verdict moins grave l'emporte
    cote_a = {"ticker": "GLD", "gravite": 0, "verdict": "Compatible", "_pire": -0.15}
    cote_b = {"ticker": "NVDA", "gravite": 3, "verdict": "Contraire à une contrainte déclarée", "_pire": -0.10}

    res = duel.decider(cote_a, cote_b)
    assert res["gagnant"] == "GLD"
    assert res["regle"] == 1
    assert "son verdict est moins grave" in res["raison"]


def test_decider_regle_2_baisse():
    # Même gravité, pire baisse plus faible l'emporte (ex: -12% vs -22%)
    cote_a = {"ticker": "XBB.TO", "gravite": 0, "verdict": "Compatible", "_pire": -0.12}
    cote_b = {"ticker": "SPY", "gravite": 0, "verdict": "Compatible", "_pire": -0.22}

    res = duel.decider(cote_a, cote_b)
    assert res["gagnant"] == "XBB.TO"
    assert res["regle"] == 2
    assert "le portefeuille baisse moins" in res["raison"]


def test_decider_regle_3_egalite():
    # Même gravité, écart de baisse inférieur à 0.5% (ECART_EGALITE)
    cote_a = {"ticker": "AAPL", "gravite": 0, "verdict": "Compatible", "_pire": -0.151}
    cote_b = {"ticker": "MSFT", "gravite": 0, "verdict": "Compatible", "_pire": -0.153}

    res = duel.decider(cote_a, cote_b)
    assert res["gagnant"] is None
    assert res["regle"] == 3
    assert "presque égales" in res["raison"]


def test_juger_duel_complet_mode_gabarit():
    p = profils.PROFILS["amira"]
    res = duel.juger_duel(p, ("QQQ", 0.10), ("NVDA", 0.10), mode="gabarit")

    assert res["profil"] == "amira"
    assert len(res["cotes"]) == 2
    assert res["cotes"][0]["ticker"] == "QQQ"
    assert res["cotes"][1]["ticker"] == "NVDA"
    assert "decision" in res
    assert "titre" in res["decision"]
    assert "debat" in res
    assert len(res["debat"]) == 3  # Avocat A, Avocat B, Le Juge
    # Le greffier n'a trouvé aucun chiffre non vérifié
    assert all(tour["non_verifies"] == [] for tour in res["debat"])
