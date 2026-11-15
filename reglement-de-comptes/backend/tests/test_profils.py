"""Tests unitaires du module rdc.profils : personas officiels et cohérence financière."""
from rdc import donnees
from rdc.profils import PROFILS, PROFILS_DICTS, Profil


def test_profils_cles_et_types():
    assert set(PROFILS.keys()) == {"amira", "mateo", "robert"}
    for cle, profil in PROFILS.items():
        assert isinstance(profil, Profil)
        assert profil.cle == cle
        assert profil.capital > 0
        assert profil.horizon_ans >= 1
        assert 0 < profil.budget_perte < 1
        assert 0 < profil.plafond_position <= 1.0
        assert 0 < profil.plafond_secteur <= 1.0
        assert profil.demande_exemple[0]
        assert 0 < profil.demande_exemple[1] <= 0.5


def test_somme_portefeuilles_et_univers():
    d = donnees.charger()
    univers_tickers = set(d.univers.index)

    for cle, profil in PROFILS.items():
        # La somme des pondérations doit faire 100%
        total_poids = sum(profil.portefeuille.values())
        assert abs(total_poids - 100) < 1e-5 or abs(total_poids - 1.0) < 1e-5, f"Poids invalide pour {cle}: {total_poids}"

        # Tous les titres doivent faire partie des 31 actifs
        for ticker in profil.portefeuille.keys():
            assert ticker in univers_tickers, f"Ticker {ticker} du profil {cle} absent de l'univers"

        # Le ticker exemple doit également être dans l'univers
        assert profil.demande_exemple[0] in univers_tickers


def test_contraintes_specifiques_amira():
    amira = PROFILS["amira"]
    assert amira.crypto_allowed is True
    assert amira.horizon_max == 25.0
    assert amira.risque == "élevé"
    assert amira.filtre_esg is False


def test_contraintes_specifiques_mateo():
    mateo = PROFILS["mateo"]
    assert mateo.filtre_esg is True
    assert mateo.esg_strict is True
    assert "Energy" in mateo.secteurs_a_justifier
    assert mateo.horizon_ans == 8
    assert mateo.horizon_max == 12.0
    assert mateo.risque == "modéré"


def test_contraintes_specifiques_robert():
    robert = PROFILS["robert"]
    assert "crypto" in robert.classes_exclues
    assert robert.crypto_allowed is False
    assert robert.budget_perte == 0.12
    assert robert.horizon_ans == 3
    assert robert.horizon_max == 5.0
    assert robert.risque == "faible à modéré"


def test_profil_to_dict_et_avec():
    amira = PROFILS["amira"]
    d = amira.to_dict()
    assert d["cle"] == "amira"
    assert d["capital"] == 40_000
    assert d["crypto_allowed"] is True

    # Test de la méthode d'immutabilité avec()
    amira_modifiee = amira.avec(capital=50_000)
    assert amira_modifiee.capital == 50_000
    assert amira.capital == 40_000  # inchangé
