"""Tests unitaires du module rdc.s3_service : connectivité S3, repli gracieux et persistance."""
import io
import json
from unittest.mock import MagicMock, patch

from rdc import s3_service


def test_obtenir_nom_bucket_et_prefixe(monkeypatch):
    monkeypatch.setenv("RDC_S3_BUCKET", "mon-bucket-test")
    monkeypatch.setenv("RDC_S3_PREFIX", "dossier_alpha/")
    assert s3_service.obtenir_nom_bucket() == "mon-bucket-test"
    assert s3_service.obtenir_prefixe_s3() == "dossier_alpha/"


def test_verifier_connexion_s3_sans_bucket(monkeypatch):
    monkeypatch.delenv("RDC_S3_BUCKET", raising=False)
    res = s3_service.verifier_connexion_s3()
    assert res["connecte"] is False
    assert res["bucket"] is None
    assert "non défini" in res["message"]


def test_sauvegarder_et_lire_sans_bucket(monkeypatch):
    monkeypatch.delenv("RDC_S3_BUCKET", raising=False)
    assert s3_service.sauvegarder_json_s3("cle.json", {"a": 1}) is False
    assert s3_service.lire_json_s3("cle.json") is None


def test_operations_s3_avec_mock(monkeypatch, tmp_path):
    mock_s3 = MagicMock()
    mock_s3.list_objects_v2.return_value = {
        "Contents": [{"Key": "alphaforge/test.json", "Size": 123}]
    }
    json_bytes = json.dumps({"statut": "succes"}).encode("utf-8")
    mock_s3.get_object.return_value = {"Body": io.BytesIO(json_bytes)}

    with patch("rdc.s3_service.obtenir_client_s3", return_value=mock_s3):
        # 1. Vérification connexion
        monkeypatch.setenv("RDC_S3_BUCKET", "mon-bucket")
        verif = s3_service.verifier_connexion_s3()
        assert verif["connecte"] is True
        assert verif["nb_objets_trouves"] == 1

        # 2. Sauvegarde JSON
        assert s3_service.sauvegarder_json_s3("test.json", {"cle": "valeur"}, bucket="mon-bucket") is True
        mock_s3.put_object.assert_called()

        # 3. Lecture JSON
        donnees = s3_service.lire_json_s3("test.json", bucket="mon-bucket")
        assert donnees == {"statut": "succes"}

        # 4. Téléversement de fichier local
        fichier_test = tmp_path / "fichier.csv"
        fichier_test.write_text("ticker,valeur\nNVDA,100", encoding="utf-8")
        assert s3_service.televerser_fichier_s3(fichier_test, "alphaforge/fichier.csv", bucket="mon-bucket") is True

        # 5. Synchronisation de dossier
        dossier_test = tmp_path / "sync_dir"
        dossier_test.mkdir()
        (dossier_test / "a.json").write_text("{}", encoding="utf-8")
        (dossier_test / "b.csv").write_text("x", encoding="utf-8")
        nb_sync = s3_service.synchroniser_dossier_s3(dossier_test, "prefixe/", bucket="mon-bucket")
        assert nb_sync == 2
