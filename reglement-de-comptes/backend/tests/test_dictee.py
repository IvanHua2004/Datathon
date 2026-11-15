"""Dictée vocale : sans identifiants AWS, l'API répond « indisponible » et le navigateur prend le relais."""
from fastapi.testclient import TestClient

import api
from rdc import dictee


def test_sigles_remis_en_tickers():
    assert dictee.nettoyer("Devrais-je placer 10 % dans S.P.Y. ?") == "Devrais-je placer 10 % dans SPY ?"
    assert dictee.nettoyer("et X.B.B. ou q.q.q.") == "et XBB ou QQQ"


def test_sans_identifiants_la_dictee_est_indisponible(monkeypatch):
    monkeypatch.setattr(dictee, "identifiants_presents", lambda: False)
    with TestClient(api.app).websocket_connect("/api/dictee") as ws:
        assert ws.receive_json()["type"] == "indisponible"


def test_vocabulaire_sans_acces_ne_bloque_pas(monkeypatch):
    import boto3

    def refuser(*args, **kwargs):
        raise RuntimeError("AccessDenied")
    monkeypatch.setattr(boto3, "client", refuser)
    dictee._etat_vocabulaire.update(nom=None, verifie=None)
    assert dictee.vocabulaire_pret() is None
