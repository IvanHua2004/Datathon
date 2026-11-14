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
    r = client.post("/api/proces", json={"profil": "robert", "ticker": "NVDA", "taille": 0.2, "mode": "gabarit"})
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


def _q(texte, **contexte):
    r = client.post("/api/questions/analyser", json={"texte": texte, "profil": "robert", **contexte})
    assert r.status_code == 200
    return r.json()


def test_question_recevable():
    a = _q("Devrais-je placer 20 % de mon portefeuille dans NVDA ?")
    assert (a["statut"], a["ticker"], a["taille"]) == ("recevable", "NVDA", 0.2)
    assert _q("Et si je mettais 10% dans la Banque Royale ?")["ticker"] == "RY.TO"
    assert _q("15 pour cent en bitcoin, raisonnable pour moi ?")["ticker"] == "BTC-USD"


def test_question_incomplete_puis_completee():
    a = _q("Que penses-tu de Shopify ?")
    assert (a["statut"], a["motif"], a["ticker"]) == ("choix", "part_manquante", "SHOP.TO")
    assert [c["taille"] for c in a["choix"]] == [0.05, 0.10, 0.20]
    b = _q("20 %", ticker="SHOP.TO")
    assert (b["statut"], b["ticker"], b["taille"]) == ("recevable", "SHOP.TO", 0.2)
    c = _q("Je veux placer 10 % de mon portefeuille")
    assert (c["statut"], c["motif"], c["taille"]) == ("incomplet", "titre_manquant", 0.1)
    assert _q("Apple", taille=0.1)["statut"] == "recevable"


def test_question_refusee():
    motifs = {
        "Devrais-je acheter 10 % de Coca-Cola ?": "hors_univers",
        "NVDA va-t-elle monter l'an prochain ?": "prediction",
        "Quel temps fera-t-il demain ?": "hors_sujet",
        "Achète 20 % de Tesla pour moi": "ordre_reel",
        "Devrais-je placer 80 % dans SPY ?": "part_invalide",
    }
    for texte, motif in motifs.items():
        a = _q(texte)
        assert (a["statut"], a["motif"]) == ("refus", motif), texte
    assert _q("Devrais-je acheter 10 % de Coca-Cola ?")["reformulations"]


def test_question_vague_propose_des_choix():
    a = _q("Est-ce que je devrais investir dans la tech ?")
    assert (a["statut"], a["motif"]) == ("choix", "theme")
    assert [c["ticker"] for c in a["choix"]][:2] == ["QQQ", "NVDA"]
    assert all(c["taille"] == 0.10 for c in a["choix"])
    crypto = _q("La crypto, c'est pour moi ?")
    assert [c["ticker"] for c in crypto["choix"]] == ["BTC-USD", "ETH-USD"] and crypto["choix"][0]["taille"] == 0.05
    assert _q("Je veux être plus prudent")["choix"][0]["ticker"] == "XBB.TO"
    assert _q("Est-ce que l'or protège mon portefeuille ?")["choix"][0]["ticker"] == "GLD"
    assert _q("20 % dans l'IA ?")["choix"][0]["taille"] == 0.2
    deux = _q("10 % dans Apple ou Microsoft ?")
    assert (deux["statut"], [c["ticker"] for c in deux["choix"]]) == ("choix", ["AAPL", "MSFT"])


def test_archiviste_donne_les_chiffres_sans_comparer():
    a = _q("c'est quoi les stats de nvidia")
    assert (a["statut"], a["agent"]) == ("fiche", "archiviste")
    fiche = a["fiches"][0]
    assert fiche["ticker"] == "NVDA" and len(fiche["faits"]) == 10
    assert [c["taille"] for c in a["choix"]] == [0.05, 0.10, 0.20]
    deux = _q("Montre-moi les chiffres de Apple et Microsoft")
    assert deux["statut"] == "comparaison" and [f["ticker"] for f in deux["fiches"]] == ["AAPL", "MSFT"]
    assert "ne dis pas lequel est meilleur" in deux["message"]
    assert [f["libelle"] for f in deux["fiches"][0]["faits"]] == [f["libelle"] for f in deux["fiches"][1]["faits"]]
    # Avec une part, c'est une décision : le greffier la juge recevable.
    assert _q("Vu son rendement, devrais-je placer 20 % dans NVDA ?")["statut"] == "recevable"


def test_archiviste_catalogue_et_selection():
    tout = _q("Quelles compagnies je peux choisir ?")
    assert (tout["statut"], tout["agent"]) == ("catalogue", "archiviste")
    assert sum(len(g["titres"]) for g in tout["groupes"]) == 31
    robert = {t["ticker"]: t for g in tout["groupes"] for t in g["titres"]}
    assert robert["XBB.TO"]["dansPortefeuille"] and robert["BTC-USD"]["exclu"]
    tech = _q("Quelles sont les compagnies tech ?")
    assert [t["ticker"] for t in tech["groupes"][0]["titres"]][:2] == ["QQQ", "NVDA"]
    assert _q("NVDA ou l'or ?")["statut"] == "comparaison"
    domaines = _q("Compare la tech et l'énergie")
    assert (domaines["statut"], domaines["selection"], len(domaines["groupes"])) == ("selection", "un_par_groupe", 2)
    trois = _q("Compare Apple, Microsoft et Tesla")
    assert (trois["statut"], trois["selection"]) == ("selection", "deux")
    # Une part dans la question : c'est une décision, le greffier propose les dossiers.
    assert _q("10 % dans Apple ou Microsoft ?")["agent"] == "greffier"
