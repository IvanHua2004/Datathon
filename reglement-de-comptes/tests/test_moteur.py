"""Tests du moteur et du procès. Lancer :  pytest -q"""
import numpy as np
import pandas as pd
import pytest

from rdc import donnees, moteur
from rdc.greffier import Greffier
from rdc.profils import PROFILS
from rdc.proces import V_CONTRAINTE, V_INDECIDABLE, V_TENSION, ouvrir_proces


def test_pire_baisse_sur_serie_connue():
    dates = pd.bdate_range("2024-01-01", periods=5)
    r = pd.Series([0.10, -0.50, 0.20, 0.70, 0.0], index=dates)   # valeur : 1,1 ; 0,55 ; 0,66 ; 1,122
    pb = moteur.pire_baisse(r)
    assert pb["profondeur"] == pytest.approx(-0.5)
    assert pb["date_sommet"] == "2024-01-01" and pb["date_creux"] == "2024-01-02"
    assert pb["recupere"] and pb["date_retour"] == "2024-01-04"


def test_ajouter_position_garde_un_total_de_un():
    p = moteur.ajouter_position({"A": 60, "B": 40}, "C", 0.2)
    assert sum(p.values()) == pytest.approx(1.0)
    assert p["C"] == pytest.approx(0.2) and p["A"] == pytest.approx(0.48)


def test_contributions_au_risque_somment_a_un():
    d = donnees.charger()
    c = moteur.contributions_risque(d.rendements, PROFILS["robert"].portefeuille)
    assert sum(c.values()) == pytest.approx(1.0)


def test_second_calcul_independant_de_la_pire_baisse():
    """Contre-calcul : la pire baisse refaite avec une boucle simple donne le même chiffre."""
    d = donnees.charger()
    r = moteur.rendements_portefeuille(d.rendements, PROFILS["robert"].portefeuille)
    valeur, sommet, pire = 1.0, 1.0, 0.0
    for x in r.to_numpy():
        valeur *= 1 + x
        sommet = max(sommet, valeur)
        pire = min(pire, valeur / sommet - 1)
    assert moteur.pire_baisse(r)["profondeur"] == pytest.approx(pire)


def test_donnees_sans_trou_et_en_cad():
    d = donnees.charger()
    assert d.prix_cad.shape[1] == 31 and not d.prix_cad.isna().any().any()
    assert (d.prix_cad.index.dayofweek < 5).all()


def test_verdicts_des_trois_demandes_types():
    attendus = {"robert": V_CONTRAINTE, "amira": V_TENSION, "mateo": V_INDECIDABLE}
    for cle, attendu in attendus.items():
        p = PROFILS[cle]
        proces = ouvrir_proces(p, *p.demande_exemple)
        assert proces.decision["verdict"] == attendu
        for plaidoirie in proces.plaidoiries + [proces.motivation]:
            assert plaidoirie.non_verifies == [], plaidoirie.texte


def test_le_greffier_repere_un_chiffre_invente():
    p = PROFILS["robert"]
    proces = ouvrir_proces(p, *p.demande_exemple)
    assert proces.greffier.verifier("La perte serait de -99,9 % [P-01].") == ["99.9"]
    assert Greffier().verifier("Aucun chiffre ici.") == []
