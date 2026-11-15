"""Tests d'intégration exhaustifs de l'ensemble des routes API du Tribunal."""
from fastapi.testclient import TestClient

from api import app

client = TestClient(app)


def test_api_sante():
    r = client.get("/api/sante")
    assert r.status_code == 200
    corps = r.json()
    assert "source" in corps
    assert "periode" in corps
    assert "debut" in corps["periode"]
    assert "fin" in corps["periode"]


def test_api_tailles():
    r = client.get("/api/tailles")
    assert r.status_code == 200
    tailles = r.json()
    assert isinstance(tailles, list)
    assert 0.05 in tailles
    assert 0.20 in tailles
    assert all(0 < t <= 0.5 for t in tailles)


def test_api_actions_liste_et_detail():
    # Liste globale des fiches actions
    r = client.get("/api/actions")
    assert r.status_code == 200
    corps = r.json()
    assert isinstance(corps, list)
    assert len(corps) == 31
    assert any(a["ticker"] == "NVDA" for a in corps)

    # Fiche individuelle existante
    r_nvda = client.get("/api/actions/NVDA")
    assert r_nvda.status_code == 200
    nvda = r_nvda.json()
    assert nvda["ticker"] == "NVDA"
    assert "rendements" in nvda
    assert "risque" in nvda
    assert "ratios_performance" in nvda
    assert "synthese_agent_llm" in nvda
    assert "tags_semantiques" in nvda

    # Fiche inconnue 404
    assert client.get("/api/actions/INCONNU").status_code == 404


def test_api_intention():
    r = client.post("/api/intention", json={
        "profil": "amira",
        "texte": "Je veux placer 15% dans du bitcoin"
    })
    assert r.status_code == 200
    corps = r.json()
    assert corps["ticker"] == "BTC-USD"
    assert corps["taille"] == 0.15
    assert "Bitcoin" in corps["nomTitre"]
    assert "explication" in corps


def test_api_duel():
    r = client.post("/api/duel", json={
        "profil": "robert",
        "a": {"ticker": "NVDA", "taille": 0.1},
        "b": {"ticker": "GLD", "taille": 0.1},
        "mode": "gabarit",
    })
    assert r.status_code == 200
    corps = r.json()
    assert corps["profil"] == "robert"
    assert len(corps["cotes"]) == 2
    assert "decision" in corps
    assert "gagnant" in corps["decision"]
    assert "debat" in corps


def test_api_comparaison():
    r = client.post("/api/comparaison", json={
        "profil": "robert",
        "ticker": "NVDA",
        "taille": 0.2,
        "choix_investisseur": "NON"
    })
    assert r.status_code == 200
    corps = r.json()
    assert corps["choix"] is False
    assert "delta_perte_dollars" in corps
    assert "statut_conformite" in corps
    assert "commentaire_conseil" in corps


def test_api_scenarios():
    r = client.post("/api/scenarios", json={
        "profil": "amira",
        "ticker": "QQQ",
        "taille": 0.2
    })
    assert r.status_code == 200
    scenarios = r.json()
    assert isinstance(scenarios, list)
    assert len(scenarios) == 3
    types_scenarios = [s["type"] for s in scenarios]
    assert "taille_reduite" in types_scenarios
    assert "fnb_diversifie" in types_scenarios
    assert "barbell" in types_scenarios


def test_api_proces_discussion_seule():
    r = client.post("/api/proces/discussion", json={
        "profil": "robert",
        "ticker": "NVDA",
        "taille": 0.2,
        "mode": "gabarit"
    })
    assert r.status_code == 200
    discussion = r.json()
    assert isinstance(discussion, list)
    assert len(discussion) >= 5
    roles = [d["role"] for d in discussion]
    assert "huissier" in roles
    assert "greffier" in roles
    assert "avocat_defense" in roles
    assert "procureur" in roles
    assert "juge" in roles


def test_api_proces_stream():
    r = client.post("/api/proces/stream", json={
        "profil": "robert",
        "ticker": "NVDA",
        "taille": 0.1,
        "mode": "gabarit"
    })
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")
    assert "data:" in r.text


def test_api_export_graphique_svg():
    r = client.get("/api/proces/export-graphique/simulations?profil=robert&ticker=NVDA&taille=0.20")
    assert r.status_code == 200
    assert "image/svg+xml" in r.headers.get("content-type", "")
    assert "<svg" in r.text


def test_api_generation_pdf():
    r = client.post("/api/pdf", json={
        "profil": "robert",
        "ticker": "NVDA",
        "taille": 0.2,
        "decision_investisseur": "NON"
    })
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
