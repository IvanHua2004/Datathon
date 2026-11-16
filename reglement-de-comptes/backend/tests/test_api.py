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
    assert any("Défense" in p["role"] for p in corps["plaidoiries"])
    assert any("Procureur" in p["role"] for p in corps["plaidoiries"])
    assert "Juge" in corps["motivation"]["role"]
    assert all(p["non_verifies"] == [] for p in corps["plaidoiries"])
    assert [p["numero"] for p in corps["pieces"]][:1] == ["P-01"]
    assert len(corps["salle"]) == 4 and len(corps["courbe"]) == 9
    assert "discussion" in corps and len(corps["discussion"]) >= 5


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


def test_archiviste_domaines_et_moyennes():
    a = _q("obbligations vs actions americaines")
    assert (a["statut"], a["agent"]) == ("selection", "archiviste")
    assert [g["nom"] for g in a["groupes"]] == ["Les obligations", "Les actions américaines"]
    assert a["groupes"][0]["titres"][0]["ticker"] == "MOY:les obligations"
    m = _q("moyenne obligations vs actions americaines")
    assert m["statut"] == "comparaison" and [f["ticker"] for f in m["fiches"]] == ["MOY:les obligations", "MOY:les actions américaines"]
    assert _q("compare la tech")["motif"] == "comparaison_incomplete"
    r = client.post("/api/questions/analyser", json={"texte": "", "profil": "robert",
                                                    "comparer": ["MOY:la crypto", "NVDA"]}).json()
    assert [f["ticker"] for f in r["fiches"]] == ["MOY:la crypto", "NVDA"] and [c["ticker"] for c in r["choix"]] == ["NVDA"]


def test_duel_deux_titres():
    r = client.post("/api/duel", json={"profil": "robert", "mode": "gabarit",
                                       "a": {"ticker": "NVDA", "taille": 0.1}, "b": {"ticker": "XBB.TO", "taille": 0.1}})
    assert r.status_code == 200
    duel = r.json()
    assert [c["ticker"] for c in duel["cotes"]] == ["NVDA", "XBB.TO"]
    assert duel["decision"]["gagnant"] in ("NVDA", "XBB.TO", None) and duel["decision"]["texte"]
    assert all(len(c["chiffres"]) == 6 for c in duel["cotes"])
    assert [t["role"] for t in duel["debat"]] == ["avocat_a", "avocat_b", "juge"]
    assert all(t["non_verifies"] == [] for t in duel["debat"])
    assert client.post("/api/duel", json={"profil": "robert", "a": {"ticker": "NVDA", "taille": 0.1},
                                          "b": {"ticker": "NVDA", "taille": 0.2}}).status_code == 422


def test_boutons_catalogue():
    tout = client.post("/api/questions/analyser", json={"texte": "", "profil": "amira", "action": "catalogue"}).json()
    assert tout["statut"] == "catalogue" and sum(len(g["titres"]) for g in tout["groupes"]) == 31
    deux = client.post("/api/questions/analyser", json={"texte": "", "profil": "amira", "action": "choisir_deux"}).json()
    assert (deux["statut"], deux["selection"]) == ("selection", "deux")


def test_memoire_de_la_conversation():
    # La part la plus récente est gardée quand on change seulement de titre.
    a = _q("et Microsoft ?", historique=["Devrais-je placer 10 % dans Apple ?"])
    assert (a["statut"], a["ticker"], a["taille"]) == ("recevable", "MSFT", 0.1)
    assert a["message"].startswith("D'après la conversation") or "Je garde la part" in a["message"]
    # Le titre le plus récent est repris quand on ne donne qu'une part.
    b = _q("plutôt 15 %", historique=["10 % dans Apple ?", "Les chiffres de NVDA"])
    assert (b["statut"], b["ticker"], b["taille"]) == ("recevable", "NVDA", 0.15)
    # « ses stats » : l'archiviste prend le dernier titre nommé.
    c = _q("et ses stats ?", historique=["Devrais-je placer 5 % dans Bitcoin ?"])
    assert (c["agent"], c["fiches"][0]["ticker"]) == ("archiviste", "BTC-USD")
    # « compare avec l'or » : l'autre côté est le titre le plus récent.
    d = _q("compare avec l'or", historique=["Les chiffres de Shopify", "Les chiffres de NVDA"], ticker="NVDA")
    assert [f["ticker"] for f in d["fiches"]] == ["NVDA", "GLD"]
    # Une nouvelle question complète ignore l'historique.
    e = _q("Devrais-je placer 20 % dans TSLA ?", historique=["10 % dans Apple ?"])
    assert (e["ticker"], e["taille"]) == ("TSLA", 0.2) and not e["message"].startswith("D'après")


def test_conversation_naturelle():
    assert _q("bonjour")["statut"] == "social"
    assert _q("recommence")["motif"] == "recommencer"
    d = _q("c'est quoi la volatilité ?")
    assert (d["agent"], d["statut"], d["definition"]["terme"]) == ("archiviste", "definition", "volatilité")
    b = _q("c'est quoi mon budget de perte ?")
    assert (b["statut"], b["agent"]) == ("profil", "archiviste") and "12 %" in b["message"]
    p = _q("qu'est-ce que j'ai dans mon portefeuille ?")
    assert p["statut"] == "profil" and {x["ticker"] for x in p["profil"]["portefeuille"]} >= {"XBB.TO", "SPY"}
    assert _q("J'aime l'IA")["theme"] == "l'intelligence artificielle"
    f = _q("10 % dans nvidai")
    assert (f["statut"], f["ticker"]) == ("recevable", "NVDA") and "nvidai" in f["message"]
    assert _q("stats de shopfy")["fiches"][0]["ticker"] == "SHOP.TO"
    assert _q("Je veux placer 10 % de mon portefeuille")["motif"] == "titre_manquant"


def test_filet_bedrock_reecrit_la_question(monkeypatch):
    """Sans appeler AWS : on simule la réponse du modèle et on vérifie le chemin complet."""
    from rdc import conversation
    monkeypatch.setattr(conversation, "classer_avec_modele",
                        lambda *a, **k: {"intention": "decision", "tickers": ["NVDA"], "part": 0.15, "terme": None})
    a = _q("je suis fan des cartes graphiques, j'en mets un peu ?")
    assert (a["statut"], a["ticker"], a["taille"]) == ("recevable", "NVDA", 0.15)
    assert a["message"].startswith("J'ai compris : « Devrais-je placer 15 % dans NVDA ? »")
    monkeypatch.setattr(conversation, "classer_avec_modele",
                        lambda *a, **k: {"intention": "hors_sujet", "tickers": [], "part": None, "terme": None})
    assert _q("raconte une blague")["motif"] == "hors_sujet"


def test_greffier_recoit_les_votes_precedents():
    votes = [
        {"type": "proces", "ticker": "NVDA", "nomTitre": "NVIDIA", "taille": 0.1, "vote": "avocat_defense",
         "verdictTribunal": "Contraire au profil", "accord": False},
        {"type": "duel", "ticker": "NVDA", "taille": 0.1, "vote": "XBB.TO", "adversaire": "XBB.TO",
         "gagnant": "XBB.TO", "verdictTribunal": "XBB.TO l'emporte"},
    ]
    r = client.post("/api/questions/analyser", json={"texte": "Qu'est-ce que j'ai voté ?", "profil": "robert",
                                                     "votes": votes}).json()
    assert r["statut"] == "votes" and r["agent"] == "archiviste"
    assert "2 débats" in r["message"] and "1 fois sur 2" in r["message"]
    assert "la Défense" in r["votes"][0]["ligne"] and "conclusion inverse" in r["votes"][0]["ligne"]
    assert "le tribunal vous rejoint" in r["votes"][1]["ligne"]

    vide = client.post("/api/questions/analyser", json={"texte": "mes votes ?", "profil": "robert"}).json()
    assert vide["statut"] == "votes" and not vide["votes"]

    # Une question normale passe toujours, votes ou pas.
    normal = client.post("/api/questions/analyser", json={"texte": "Devrais-je placer 10 % dans SPY ?",
                                                          "profil": "robert", "votes": votes}).json()
    assert normal["statut"] == "recevable"
