"""Persona personnalisé : la note décrit-elle assez le portefeuille ?"""
import api
from rdc import questions

UNIVERS = {"SPY": "SPDR S&P 500 ETF Trust", "XBB.TO": "iShares Core Canadian Universe Bond Index ETF",
           "AAPL": "Apple", "BTC-USD": "Bitcoin"}


def test_note_detaillee_donne_le_portefeuille():
    assert api.portefeuille_depuis_note("SPY 60 %, 40 % en XBB.TO", UNIVERS) == {"SPY": 60.0, "XBB.TO": 40.0}


def test_note_vague_ou_incomplete_ne_donne_rien():
    assert api.portefeuille_depuis_note("Je préfère éviter la crypto.", UNIVERS) == {}
    assert api.portefeuille_depuis_note("Apple 30 %, Bitcoin 20 %", UNIVERS) == {}   # 50 % seulement


def test_persona_vague_utilise_le_portefeuille_de_reference():
    persona = api.PersonaPersonnalise(nom="Léa", age=30, risque="modere", horizon_min=5, horizon_max=10,
                                      note="Je préfère éviter la crypto.")
    profil = persona.creer_profil(UNIVERS)
    assert not profil.portefeuille_declare
    assert profil.mot_portefeuille == "le portefeuille de référence"
    detaille = persona.model_copy(update={"note": "SPY 60 %, XBB.TO 40 %"}).creer_profil(UNIVERS)
    assert detaille.portefeuille_declare and detaille.portefeuille == {"SPY": 60.0, "XBB.TO": 40.0}


def test_le_greffier_ne_dit_pas_votre_portefeuille():
    texte = questions.sans_votre_portefeuille(
        "Quelle part de votre portefeuille ? Devrais-je placer 10 % de mon portefeuille dans SPY ?")
    assert "votre portefeuille" not in texte and "mon portefeuille" not in texte
    assert texte == ("Quelle part du portefeuille de référence ? "
                     "Devrais-je placer 10 % du portefeuille de référence dans SPY ?")


def test_oublier_le_persona_efface_le_cookie():
    from fastapi.testclient import TestClient
    client = TestClient(api.app)
    r = client.post("/api/profils/personnalise", json={"nom": "Léa", "age": 30, "risque": "modere",
                                                       "horizon_min": 5, "horizon_max": 10, "note": ""})
    assert r.status_code == 200 and client.cookies.get("rdc_persona")
    assert client.delete("/api/profils/personnalise").status_code == 204
    assert not client.cookies.get("rdc_persona")
    assert all(p["cle"] != "personnalise" for p in client.get("/api/profils").json())


def test_persona_mineur_refuse():
    from fastapi.testclient import TestClient
    client = TestClient(api.app)
    base = {"nom": "Léo", "risque": "modere", "horizon_min": 5, "horizon_max": 10, "note": ""}
    assert client.post("/api/profils/personnalise", json={**base, "age": 17}).status_code == 422
    assert client.post("/api/profils/personnalise", json={**base, "age": 18}).status_code == 200
