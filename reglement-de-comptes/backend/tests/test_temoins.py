"""Tests unitaires du module rdc.temoins : déposition sous serment de tous les experts."""
import pytest
from rdc import donnees, proces, profils, temoins
from rdc.greffier import Greffier, Piece


@pytest.fixture(scope="module")
def dossier_robert_nvda():
    p = profils.PROFILS["robert"]
    return proces.construire_dossier(p, "NVDA", 0.2)


def test_dictionnaire_temoins():
    assert set(temoins.TEMOINS.keys()) == {
        "risque", "diversification", "valeurs", "macro", "action", "simulation"
    }
    assert set(temoins.DESCRIPTIONS.keys()) == set(temoins.TEMOINS.keys())


def test_temoin_risque(dossier_robert_nvda):
    greffier = Greffier()
    piece = temoins.risque(dossier_robert_nvda, greffier, appele_par="la Défense")
    assert isinstance(piece, Piece)
    assert piece.numero == "P-01"
    assert piece.temoin == "risque"
    assert "Pire baisse observée, avec la position" in piece.faits
    assert "Perte en dollars au pire creux, avec la position" in piece.faits
    assert "Budget de perte déclaré (hypothèse du profil)" in piece.faits
    assert "Volatilité annuelle, avec la position" in piece.faits
    assert piece.source
    assert piece.periode
    assert piece.limites


def test_temoin_diversification(dossier_robert_nvda):
    greffier = Greffier()
    piece = temoins.diversification(dossier_robert_nvda, greffier, appele_par="le Procureur")
    assert isinstance(piece, Piece)
    assert piece.numero == "P-01"
    assert piece.temoin == "diversification"
    assert any("Rendement moyen" in k for k in piece.faits)
    assert any("Poids du secteur" in k for k in piece.faits)
    assert any("Exposition au dollar américain" in k for k in piece.faits)
    assert piece.limites


def test_temoin_valeurs(dossier_robert_nvda):
    greffier = Greffier()
    piece = temoins.valeurs(dossier_robert_nvda, greffier, appele_par="le Procureur")
    assert isinstance(piece, Piece)
    assert piece.temoin == "valeurs"
    assert any("Preuves ESG collectées pour NVDA" in k for k in piece.faits)


def test_temoin_macro(dossier_robert_nvda):
    greffier = Greffier()
    piece = temoins.macro(dossier_robert_nvda, greffier, appele_par="le Procureur")
    assert isinstance(piece, Piece)
    assert piece.temoin == "macro"
    assert any("Taux directeur" in k for k in piece.faits)


def test_temoin_action(dossier_robert_nvda):
    greffier = Greffier()
    piece = temoins.action_temoin(dossier_robert_nvda, greffier, appele_par="l'Analyste")
    assert isinstance(piece, Piece)
    assert piece.temoin == "action"
    assert "Ratio de Sharpe de NVDA" in piece.faits
    assert "Bêta par rapport au S&P 500 (SPY CAD) de NVDA" in piece.faits
    assert "Value at Risk quotidienne 95 % (VaR) de NVDA" in piece.faits


def test_temoin_simulation(dossier_robert_nvda):
    greffier = Greffier()
    piece = temoins.simulation(dossier_robert_nvda, greffier, appele_par="l'Actuaire")
    assert isinstance(piece, Piece)
    assert piece.temoin == "simulation"
    assert "Capital engagé de départ" in piece.faits
    assert "Pire cas de perte (Stress-test historique)" in piece.faits
    assert "Cas probable / moyen (Rendement 1 an)" in piece.faits
    assert "Meilleur cas de gain (Rallye haussier 1 an)" in piece.faits
    assert "Statut de conformité du pire cas" in piece.faits
