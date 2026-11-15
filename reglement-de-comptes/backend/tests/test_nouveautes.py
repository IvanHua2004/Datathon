"""Tests unitaires automatisés des fonctionnalités avancées :
- Interprétation d'intention en langage naturel (intention.py)
- Analyse comparative d'arbitrage OUI / NON (comparaison.py)
- Générateur de scénarios alternatifs quantifiés (scenarios.py)
- Générateur du rapport officiel PDF du Greffier (rapport_pdf.py)
- Timeline théâtralisée du débat contradictoire (proces.py)
"""
from __future__ import annotations

import pytest

from rdc import donnees, intention, comparaison, scenarios, rapport_pdf, proces
from rdc.profils import PROFILS
from rdc.proces import ouvrir_proces, construire_dossier, regle_verdict, construire_timeline_discussion


@pytest.fixture(scope="module")
def data_marche():
    return donnees.charger()


def test_interpreter_intention_etf(data_marche):
    """Vérifie qu'une demande générique d'ETF est résolue selon les affinités du profil."""
    profil_amira = PROFILS["amira"]
    ticker, taille, explication = intention.interpreter_intention(
        "devrais acheter +30% dans des etf ?", data_marche.univers, profil_amira
    )
    assert ticker == "QQQ"  # Amira privilégie la croissance tech
    assert taille == pytest.approx(0.30)
    assert "30 %" in explication and "QQQ" in explication

    profil_robert = PROFILS["robert"]
    ticker_r, taille_r, expl_r = intention.interpreter_intention(
        "acheter 15% d'etf obligataire", data_marche.univers, profil_robert
    )
    assert ticker_r in ["XBB.TO", "ZST.TO", "AGG", "TLT"]
    assert taille_r == pytest.approx(0.15)


def test_interpreter_intention_ticker_direct(data_marche):
    """Vérifie l'extraction directe d'un ticker et d'une taille."""
    profil = PROFILS["mateo"]
    ticker, taille, explication = intention.interpreter_intention(
        "Je voudrais placer 25% dans NVDA svp", data_marche.univers, profil
    )
    assert ticker == "NVDA"
    assert taille == pytest.approx(0.25)


def test_comparer_decision_oui_versus_non(data_marche):
    """Vérifie les métriques calculées pour les choix OUI et NON."""
    profil = PROFILS["robert"]
    dossier = construire_dossier(profil, "NVDA", 0.20)
    decision = regle_verdict(dossier)

    # Choix OUI : investit malgré le verdict contraire
    comp_oui = comparaison.comparer_decision(dossier, decision, choix_investisseur=True)
    assert comp_oui.choix is True
    assert "Divergence" in comp_oui.statut_conformite
    assert comp_oui.delta_perte_dollars < 0  # aggravation de la perte max
    assert comp_oui.perte_max_dollars < 0
    assert len(comp_oui.recommandations) >= 2

    # Choix NON : renonce et respecte la contrainte
    comp_non = comparaison.comparer_decision(dossier, decision, choix_investisseur=False)
    assert comp_non.choix is False
    assert "Protection du capital" in comp_non.statut_conformite
    assert comp_non.delta_perte_dollars == 0.0
    assert comp_non.budget_depasse is False


def test_generer_scenarios_alternatifs(data_marche):
    """Vérifie la génération de 3 scénarios alternatifs adaptés au profil."""
    profil = PROFILS["amira"]
    dossier = construire_dossier(profil, "NVDA", 0.30)
    decision = regle_verdict(dossier)

    alts = scenarios.generer_scenarios_alternatifs(dossier, decision, "acheter 30% de NVDA")
    assert len(alts) == 3

    # Scénario 1 : taille réduite
    s1 = alts[0]
    assert s1["type"] == "taille_reduite"
    assert "NVDA" in s1["allocation"]
    assert s1["allocation"]["NVDA"] <= profil.plafond_position

    # Scénario 2 : FNB diversifié
    s2 = alts[1]
    assert s2["type"] == "fnb_diversifie"
    assert "FNB" in s2["nom"] or "diversifié" in s2["description"]

    # Scénario 3 : Haltère
    s3 = alts[2]
    assert s3["type"] in ["barbell", "haltere"]
    assert "ZST.TO" in s3["allocation"]


def test_generer_pdf_officiel(data_marche):
    """Vérifie la génération binaire correcte du PDF certifié du Greffier."""
    profil = PROFILS["mateo"]
    p = ouvrir_proces(profil, "ENB.TO", 0.20)
    alts = scenarios.generer_scenarios_alternatifs(p.dossier, p.decision)

    pdf_bytes = rapport_pdf.generer_pdf_rapport(
        proces=p,
        decision_investisseur=False,
        scenarios_alternatifs=alts,
        intention_texte="Investir 20% dans Enbridge"
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF")


def test_timeline_discussion_chronologique(data_marche):
    """Vérifie l'ordonnancement complet des 8 prises de parole de l'audience."""
    profil = PROFILS["robert"]
    p = ouvrir_proces(profil, "NVDA", 0.20)
    timeline = construire_timeline_discussion(p)

    assert len(timeline) >= 8

    # Vérification des étapes chronologiques
    etapes = [t["etape"] for t in timeline]
    assert "HUISSIER_OUVERTURE" in etapes
    assert "GREFFIER_DEPOT" in etapes
    assert "TEMOIN" in etapes
    assert "PLAIDOIRIE_DEFENSE" in etapes
    assert "AUDIT_GREFFIER_DEFENSE" in etapes
    assert "REQUISITOIRE_PROCUREUR" in etapes
    assert "AUDIT_GREFFIER_PROCUREUR" in etapes
    assert "VERDICT_JUGE" in etapes

    # Vérification des rôles et avatars
    huissier = next(t for t in timeline if t["etape"] == "HUISSIER_OUVERTURE")
    assert huissier["role"] == "huissier" and huissier["avatar"] == "📢"

    greffier = next(t for t in timeline if t["etape"] == "GREFFIER_DEPOT")
    assert greffier["role"] == "greffier" and greffier["avatar"] == "📜"

    defense = next(t for t in timeline if t["etape"] == "PLAIDOIRIE_DEFENSE")
    assert defense["role"] == "avocat_defense" and defense["avatar"] == "💼"

    procureur = next(t for t in timeline if t["etape"] == "REQUISITOIRE_PROCUREUR")
    assert procureur["role"] == "procureur" and procureur["avatar"] == "🛡️"

    juge = next(t for t in timeline if t["etape"] == "VERDICT_JUGE")
    assert juge["role"] == "juge" and juge["avatar"] == "👨‍⚖️"
    assert "verdict" in juge
