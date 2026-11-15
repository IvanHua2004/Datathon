"""Tests unitaires du module rdc.archiviste : restitution factuelle et neutre des chiffres du marché."""
import pytest
from rdc import archiviste


def test_regex_intentions_archiviste():
    # Détection demande de chiffres
    assert archiviste.demande_des_chiffres("donne-moi les stats de nvidia")
    assert archiviste.demande_des_chiffres("combien a perdu shopify ?")
    assert not archiviste.demande_des_chiffres("devrais-je acheter du bitcoin")

    # Détection demande de catalogue
    assert archiviste.demande_le_catalogue("quelles sont les compagnies disponibles ?")
    assert archiviste.demande_le_catalogue("montre-moi la liste de tous les titres")
    assert not archiviste.demande_le_catalogue("quelle heure est-il")

    # Détection demande de comparaison
    assert archiviste.demande_une_comparaison("compare apple et microsoft")
    assert archiviste.demande_une_comparaison("nvda vs shopify")
    assert not archiviste.demande_une_comparaison("parle-moi de spy")


def test_fiche_titre_individuel():
    f = archiviste.fiche("NVDA")
    assert f.ticker == "NVDA"
    assert f.nomTitre == "NVIDIA"
    assert f.devise == "USD"
    assert len(f.faits) == 10
    libelles = [fait.libelle for fait in f.faits]
    assert "Valeur au début" in libelles
    assert "Valeur à la fin" in libelles
    assert "Variation sur la période" in libelles
    assert "Volatilité annuelle" in libelles
    assert "Pire baisse" in libelles


def test_repondre_titre_seul():
    rep = archiviste.repondre("SHOP.TO")
    assert rep["agent"] == "archiviste"
    assert "sans les interpréter" in rep["message"]
    assert len(rep["fiches"]) == 1
    assert rep["fiches"][0]["ticker"] == "SHOP.TO"


def test_comparer_deux_titres():
    rep = archiviste.comparer("AAPL", "MSFT")
    assert rep["agent"] == "archiviste"
    assert "Je ne dis pas lequel est meilleur" in rep["message"]
    assert len(rep["fiches"]) == 2
    assert rep["fiches"][0]["ticker"] == "AAPL"
    assert rep["fiches"][1]["ticker"] == "MSFT"
    faits_a = [f["libelle"] for f in rep["fiches"][0]["faits"]]
    faits_b = [f["libelle"] for f in rep["fiches"][1]["faits"]]
    assert faits_a == faits_b


def test_catalogue_complet():
    cat = archiviste.catalogue()
    assert cat["agent"] == "archiviste"
    assert "groupes" in cat
    assert len(cat["groupes"]) >= 4
    total_titres = sum(len(g["titres"]) for g in cat["groupes"])
    assert total_titres == 31


def test_fiche_moyenne_domaine():
    f = archiviste.fiche_moyenne("la technologie")
    assert f.ticker == "MOY:la technologie"
    assert "Moyenne" in f.nomTitre
    assert len(f.faits) == 10
    assert "indice, départ 100" in f.faits[0].valeur
