"""Tests unitaires pour l'agent vulgarisateur (analogie)."""
from api import obtenir_analogie, DemandeAnalogie, ReponseAnalogie
from rdc.agents import generer_analogie, analogies_statiques


def test_analogies_statiques_mots_cles():
    # VaR / Expected Shortfall
    var_text = "La Value at Risk quotidienne à 95% est élevée avec un Expected Shortfall inquiétant."
    analogie = analogies_statiques(var_text)
    assert "airbag" in analogie.lower() or "choc" in analogie.lower()

    # Sharpe
    sharpe_text = "L'actif affiche un ratio de Sharpe de 0.85 et une prime de risque intéressante."
    analogie_sharpe = analogies_statiques(sharpe_text)
    assert "voiture" in analogie_sharpe.lower() or "vitesse" in analogie_sharpe.lower()

    # Perte / creux
    perte_text = "La pire baisse observée pic-au-creux atteint -35%, dépassant le budget de perte."
    analogie_perte = analogies_statiques(perte_text)
    assert "corde" in analogie_perte.lower() or "vide" in analogie_perte.lower() or "gouffre" in analogie_perte.lower()

    # Diversification
    div_text = "Les 10% pires séances montrent une concentration excessive dans un seul secteur."
    analogie_div = analogies_statiques(div_text)
    assert "panier" in analogie_div.lower() or "œufs" in analogie_div.lower() or "provisions" in analogie_div.lower()

    # Macro / Taux
    macro_text = "La hausse des taux de la Banque du Canada et l'inflation modifient les corrélations."
    analogie_macro = analogies_statiques(macro_text)
    assert "gravité" in analogie_macro.lower() or "pesanteur" in analogie_macro.lower() or "taux" in analogie_macro.lower()


def test_generer_analogie_mode_gabarit():
    res = generer_analogie("Le ratio de Sharpe est de 0.42", acteur="Dr. Laurent", mode="gabarit")
    assert "analogie" in res and len(res["analogie"]) > 20
    assert res["source"] == "gabarit"


def test_generer_analogie_mode_bedrock_fallback():
    # En environnement sans connexion AWS, doit se replier sans planter
    res = generer_analogie("La pire baisse est de -25%", acteur="Me Austère", role="procureur", mode="bedrock")
    assert "analogie" in res and len(res["analogie"]) > 20
    assert res["source"] in ("bedrock", "gabarit")


def test_endpoint_analogie_route():
    demande = DemandeAnalogie(
        texte="La Value at Risk 95% et la pire baisse de 28% dépassent la tolérance au risque.",
        acteur="Dr. Laurent (Expert Actuaire)",
        role="temoin",
        mode="gabarit",
    )
    reponse = obtenir_analogie(demande)
    assert isinstance(reponse, ReponseAnalogie)
    assert "analogie" in reponse.model_dump()
    assert len(reponse.analogie) > 20
    assert "L'Analogie du Juré" in reponse.titre
    assert "Dr. Laurent" in reponse.titre
    assert reponse.source == "gabarit"
