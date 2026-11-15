"""Tests unitaires automatisés pour l'Agent Simulateur Financier (rdc/simulateur.py)."""
from __future__ import annotations

import pytest
from reportlab.graphics.shapes import Drawing

from rdc import donnees, profils, proces, simulateur, temoins, greffier, rapport_pdf
from rdc.profils import PROFILS
from rdc.proces import ouvrir_proces, construire_dossier


@pytest.fixture(scope="module")
def data_marche():
    return donnees.charger()


def test_simulation_impact_robert_nvda(data_marche):
    """Vérifie le calcul rigoureux des 3 scénarios (Pire, Moyen, Meilleur) pour Robert et NVDA."""
    profil = PROFILS["robert"]
    dossier = construire_dossier(profil, "NVDA", 0.20)
    simu = simulateur.simuler_impact_decision(dossier)

    # 1. Données de base
    assert simu.capital_initial == 600_000.0
    assert simu.budget_perte_pct == pytest.approx(0.12)
    assert simu.budget_perte_dollars == pytest.approx(72_000.0)
    assert simu.ticker == "NVDA"
    assert simu.taille == pytest.approx(0.20)

    # 2. Pire cas de perte
    pire = simu.pire_cas
    assert pire.type_scenario == "pire_perte"
    assert pire.rendement_pct < -0.20  # ~ -22.2 %
    assert pire.impact_dollars < -120_000.0  # ~ -133 070 $
    assert pire.capital_final == pytest.approx(simu.capital_initial + pire.impact_dollars)
    assert pire.capital_final < 500_000.0
    assert pire.conforme_budget is False  # Violation du budget de 12%
    assert pire.depassement_budget_dollars > 50_000.0  # Dépassement de ~61 070 $
    assert pire.date_debut == "2021-12-27"
    assert pire.date_fin == "2022-10-12"

    # 3. Cas probable / moyen
    moyen = simu.cas_probable
    assert moyen.type_scenario == "probable_moyen"
    assert moyen.rendement_pct > 0.10  # ~ +16.2 % / an
    assert moyen.impact_dollars > 50_000.0
    assert moyen.capital_final > 650_000.0
    assert moyen.capital_final == pytest.approx(simu.capital_initial + moyen.impact_dollars)
    assert moyen.conforme_budget is True

    # 4. Meilleur cas de gain
    meilleur = simu.meilleur_cas
    assert meilleur.type_scenario == "meilleur_gain"
    assert meilleur.rendement_pct > moyen.rendement_pct
    assert meilleur.rendement_pct > 0.40  # ~ +51.0 %
    assert meilleur.impact_dollars > 200_000.0  # ~ +305 888 $
    assert meilleur.capital_final > 800_000.0
    assert meilleur.capital_final == pytest.approx(simu.capital_initial + meilleur.impact_dollars)
    assert len(meilleur.date_debut) == 10 and len(meilleur.date_fin) == 10

    # 5. Comparaison avec le portefeuille actuel
    assert "pire_baisse_pct" in simu.avant
    assert "cagr_pct" in simu.avant
    assert pire.delta_vs_actuel_dollars < 0  # Perte plus profonde que le statu quo

    # 6. Synthèse textuelle
    assert "Expert Simulateur" in simu.synthese_agent
    assert "NVDA" in simu.synthese_agent


def test_deposition_simulateur(data_marche):
    """Vérifie la génération de la déposition assermentée de l'Agent Simulateur."""
    profil = PROFILS["mateo"]
    dossier = construire_dossier(profil, "XOM", 0.15)
    simu = simulateur.simuler_impact_decision(dossier)
    deposition = simulateur.generer_deposition_simulateur(simu)

    assert "Expert Simulateur Financier" in deposition
    assert "PIRE CAS DE PERTE" in deposition
    assert "CAS PROBABLE MOYEN" in deposition
    assert "MEILLEUR CAS DE GAIN" in deposition
    assert "1 304 séances" in deposition


def test_graphique_vectoriel_reportlab(data_marche):
    """Vérifie la génération du composant graphique Drawing de ReportLab."""
    profil = PROFILS["amira"]
    dossier = construire_dossier(profil, "QQQ", 0.25)
    simu = simulateur.simuler_impact_decision(dossier)

    drawing = simulateur.creer_graphique_simulations(simu)
    assert isinstance(drawing, Drawing)
    assert drawing.width == 540
    assert drawing.height == 215
    assert len(drawing.contents) > 10


def test_temoin_simulation_dans_proces(data_marche):
    """Vérifie que le témoin simulation dépose correctement sa pièce auprès du greffier."""
    profil = PROFILS["robert"]
    p = ouvrir_proces(profil, "NVDA", 0.20)

    # Vérification que la simulation est bien rattachée au procès
    assert hasattr(p, "simulation") and p.simulation is not None

    # Témoin simulation déposé
    pieces_temoins = [piece.temoin for piece in p.greffier.pieces]
    assert "simulation" in pieces_temoins

    piece_sim = next(piece for piece in p.greffier.pieces if piece.temoin == "simulation")
    assert "Capital engagé de départ" in piece_sim.faits
    assert "Pire cas de perte (Stress-test historique)" in piece_sim.faits
    assert "Cas probable / moyen (Rendement 1 an)" in piece_sim.faits
    assert "Meilleur cas de gain (Rallye haussier 1 an)" in piece_sim.faits


def test_pdf_comprend_section_simulation(data_marche):
    """Vérifie que le rapport PDF officiel contient bien le graphique et les données de simulation."""
    profil = PROFILS["robert"]
    p = ouvrir_proces(profil, "NVDA", 0.20)

    pdf_bytes = rapport_pdf.generer_pdf_rapport(
        proces=p,
        decision_investisseur=True,
        intention_texte="Investir 20% dans NVDA"
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 8000
    assert pdf_bytes.startswith(b"%PDF")


def test_temoins_agents_incarnes_et_audit(data_marche):
    """Vérifie que tous les témoins sont des personnages incarnés audités par le greffier."""
    from rdc import agents
    profil = PROFILS["robert"]
    p = ouvrir_proces(profil, "NVDA", 0.20, mode="gabarit")
    depositions = agents.depositions_temoins_incarnee(p)

    temoins_presents = {dep["temoin"] for dep in depositions}
    assert "risque" in temoins_presents
    assert "simulation" in temoins_presents
    assert "diversification" in temoins_presents

    for dep in depositions:
        assert "personnage" in dep
        assert "piece" in dep
        assert "texte" in dep
        assert len(dep["texte"]) > 20
        assert "non_verifies" in dep
        # En mode gabarit, aucun chiffre n'est inventé : audit 100% conforme
        assert len(dep["non_verifies"]) == 0
