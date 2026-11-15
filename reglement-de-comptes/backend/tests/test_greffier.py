"""Tests unitaires du module rdc.greffier : scellage des pièces, vérification et audit anti-hallucination."""
from rdc import greffier, proces, profils
from rdc.greffier import Greffier, Piece, nombres_dans


def test_nombres_dans():
    assert nombres_dans("Un rendement de 12,5 % et une perte de -45 000 $ en 2022.") == {
        "12.5", "45000", "2022"
    }
    assert nombres_dans("Aucun chiffre ici") == set()
    assert "3.14" in nombres_dans("Valeur : 3,14 ou 3.14")


def test_piece_en_texte():
    piece = Piece(
        numero="P-01",
        temoin="risque",
        outil="rdc.moteur.resume",
        parametres={"ticker": "NVDA"},
        faits={"Pire baisse": "-25,0 %", "Volatilité": "30,0 %"},
        source="prix_daily.csv",
        periode="2021 à 2026",
        limites="Passé observé",
        appele_par="la Défense",
        horodatage="2026-11-15T12:00:00",
    )
    texte = piece.en_texte()
    assert "[P-01] Témoin risque (convoqué par la Défense)" in texte
    assert "- Pire baisse : -25,0 %" in texte
    assert "Source : prix_daily.csv" in texte


def test_greffier_depot_et_unicite():
    g = Greffier()
    p1 = g.deposer(
        temoin="risque",
        outil="outil_test",
        parametres={},
        faits={"Faits A": "10 %"},
        source="source_test",
        periode="2021-2026",
        limites="",
        appele_par="Defense",
    )
    assert p1.numero == "P-01"
    assert len(g.pieces) == 1

    # Un même témoin qui redépose doit renvoyer la pièce existante sans doublon
    p1_bis = g.deposer(
        temoin="risque",
        outil="outil_test2",
        parametres={},
        faits={"Faits B": "20 %"},
        source="source_test",
        periode="2021-2026",
        limites="",
        appele_par="Defense",
    )
    assert p1_bis is p1
    assert len(g.pieces) == 1

    # Un deuxième témoin reçoit le numéro P-02
    p2 = g.deposer(
        temoin="diversification",
        outil="outil_test",
        parametres={},
        faits={"Faits C": "30 %"},
        source="source_test",
        periode="2021-2026",
        limites="",
        appele_par="Procureur",
    )
    assert p2.numero == "P-02"
    assert len(g.pieces) == 2


def test_greffier_verification_anti_hallucination():
    g = Greffier()
    g.admettre("100 000 $", "20 %")  # Chiffres du profil et de la demande
    g.deposer(
        temoin="risque",
        outil="moteur",
        parametres={},
        faits={"Pire baisse": "-15,5 %", "Perte": "-15 500 $"},
        source="donnees",
        periode="2021-2026",
        limites="",
        appele_par="Defense",
    )

    # Discours conforme : tous les chiffres figurent dans la pièce ou dans les nombres admis
    discours_valide = "Avec un capital de 100 000 $, la pire baisse est de -15,5 % [P-01], soit -15 500 $ [P-01]."
    assert g.verifier(discours_valide) == []

    # Discours avec chiffre inventé / non certifié
    discours_hallucine = "La pire baisse est de -15,5 % [P-01], mais les gains futurs atteindront 42,0 % !"
    non_verifies = g.verifier(discours_hallucine)
    assert "42.0" in non_verifies


def test_generer_rapport_explicabilite():
    pr = proces.ouvrir_proces(profils.PROFILS["robert"], "NVDA", 0.2, mode="gabarit")
    rapport = greffier.generer_rapport_explicabilite(pr)

    assert "carte_decision_auditee" in rapport
    carte = rapport["carte_decision_auditee"]
    assert carte["investisseur"]["nom"] == "Robert"
    assert carte["demande"]["ticker"] == "NVDA"
    assert carte["demande"]["taille"] == 0.2
    assert "verdict" in carte
    assert "pieces_justificatives" in carte
    assert len(carte["pieces_justificatives"]) >= 1
    assert "audit_greffier" in carte
    assert carte["audit_greffier"]["taux_verification_chiffres"] == "100%"
