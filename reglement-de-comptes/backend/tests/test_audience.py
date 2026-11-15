"""L'archiviste répond sur l'audience plaidée, à partir des pièces seulement, sans trancher."""
from rdc import audience

AUDIENCE = {
    "ticker": "SPY",
    "nomTitre": "SPDR S&P 500 ETF Trust",
    "taille": 0.1,
    "pieces": [
        {"numero": "P-01", "temoin": "risque", "description": "pertes observées",
         "faits": [{"libelle": "Part du risque total portée par SPY", "valeur": "37,6 %"},
                   {"libelle": "Perte en dollars au pire creux, avec la position", "valeur": "-69 100 $"}],
         "source": "prix ajustés", "periode": "2021-11-15 au 2026-11-12", "limites": "passé observé"},
        {"numero": "P-02", "temoin": "diversification", "description": "pires jours",
         "faits": [{"libelle": "Rendement moyen de SPY ces jours-là", "valeur": "-1,25 %"}],
         "source": "prix ajustés", "periode": "2021-11-15 au 2026-11-12", "limites": ""},
    ],
    "plaidoiries": [
        {"camp": "defense", "texte": "La demande reste mesurée [P-01].", "nonVerifies": []},
        {"camp": "accusation", "texte": "SPY accaparerait 37,6 % du risque [P-01] ! Il recule de -1,25 % [P-02]. "
                                        "Et 42,0 % des gains disparaîtraient !", "nonVerifies": ["42,0 %"]},
    ],
}


def test_ne_tranche_jamais():
    r = audience.repondre("Qui a gagné le débat ?", AUDIENCE)
    assert "Je ne tranche pas" in r.message and "le Procureur s'appuie sur [P-01], [P-02]" in r.message


def test_retrouve_la_piece_d_un_chiffre():
    r = audience.repondre("D'où vient le 37,6 % du procureur ?", AUDIENCE)
    assert "P-01" in r.message and "cité par le Procureur" in r.message
    assert r.extraits[0]["faits"] == [{"libelle": "Part du risque total portée par SPY", "valeur": "37,6 %"}]
    assert "-69 100 $" in audience.repondre("le -69 100 $ c'est quoi ?", AUDIENCE).message


def test_chiffre_non_verifie():
    r = audience.repondre("D'où vient le 42,0 % ?", AUDIENCE)
    assert "aucune pièce scellée" in r.message


def test_piece_et_camp():
    assert audience.repondre("Que contient P-02 ?", AUDIENCE).extraits[0]["numero"] == "P-02"
    r = audience.repondre("Sur quoi s'appuie le procureur ?", AUDIENCE)
    assert "P-01, P-02" in r.message and "42,0 %" in r.message


def test_question_sur_le_debat_ou_nouvelle_demande():
    assert audience.concerne_le_debat("D'où vient le 37,6 % ?", AUDIENCE)
    assert audience.concerne_le_debat("C'est quoi la part du risque ?", AUDIENCE)
    assert not audience.concerne_le_debat("Et avec 5 % ?", AUDIENCE)
    assert not audience.concerne_le_debat("Devrais-je placer 20 % dans SPY ?", AUDIENCE)
