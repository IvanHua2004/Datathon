"""Tests de l'API. Lancer depuis le dossier du projet :  pytest -q backend/tests"""
from fastapi.testclient import TestClient

from api import app

client = TestClient(app)


def test_profils_et_actifs():
    profils = client.get("/api/profils").json()
    assert {p["cle"] for p in profils} == {"amira", "mateo", "robert"}
    robert = next(p for p in profils if p["cle"] == "robert")
    assert abs(sum(x["poids"] for x in robert["portefeuille"]) - 1) < 1e-9
    actifs = client.get("/api/actifs").json()
    assert len(actifs) == 31 and any(a["ticker"] == "NVDA" for a in actifs)


def test_proces_robert_nvda():
    r = client.post("/api/proces", json={"profil": "robert", "ticker": "NVDA", "taille": 0.2})
    assert r.status_code == 200
    corps = r.json()
    assert corps["decision"]["verdict"] == "Contraire à une contrainte déclarée"
    assert [p["role"] for p in corps["plaidoiries"]] == ["La Défense", "Le Procureur"]
    assert corps["motivation"]["role"] == "Le Juge"
    assert all(p["non_verifies"] == [] for p in corps["plaidoiries"])
    assert [p["numero"] for p in corps["pieces"]][:1] == ["P-01"]
    assert len(corps["salle"]) == 4 and len(corps["courbe"]) == 9


def test_erreurs():
    assert client.post("/api/proces", json={"profil": "personne", "ticker": "NVDA", "taille": 0.2}).status_code == 404
    assert client.post("/api/proces", json={"profil": "robert", "ticker": "XXX", "taille": 0.2}).status_code == 404
    assert client.post("/api/proces", json={"profil": "robert", "ticker": "NVDA", "taille": 0.9}).status_code == 422
