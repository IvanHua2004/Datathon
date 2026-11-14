"""Module de connexion et persistance avec la base de données S3 d'AWS.

Permet le stockage, le chargement et la synchronisation des données de marché
et des fiches d'actifs précalculées (JSON, CSV, Parquet) pour éviter aux agents
de recalculer l'analyse complète à chaque exécution.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent


def _charger_env() -> None:
    """Charge les variables du fichier .env racine s'il existe et si non définies."""
    for dossier in [RACINE.parent, RACINE]:
        chemin = dossier / ".env"
        if chemin.exists():
            with open(chemin, encoding="utf-8") as f:
                for ligne in f:
                    ligne = ligne.strip()
                    if ligne and not ligne.startswith("#") and "=" in ligne:
                        k, v = ligne.split("=", 1)
                        k, v = k.strip(), v.strip().strip("\"'")
                        if k not in os.environ:
                            os.environ[k] = v
            break


_charger_env()


def obtenir_nom_bucket() -> str | None:
    """Retourne le nom du bucket configuré dans l'environnement."""
    return os.environ.get("RDC_S3_BUCKET")


def obtenir_prefixe_s3() -> str:
    """Retourne le préfixe configuré pour le bucket (ex: alphaforge/ ou extracted_actions/)."""
    return os.environ.get("RDC_S3_PREFIX", "alphaforge/")


def obtenir_client_s3(timeout_court: bool = False):
    """Initialise et retourne le client boto3 S3."""
    _charger_env()
    import boto3
    from botocore.config import Config

    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    if timeout_court:
        config = Config(connect_timeout=1, read_timeout=2, retries={"max_attempts": 1})
    else:
        config = Config(connect_timeout=3, read_timeout=8, retries={"mode": "adaptive", "max_attempts": 3})
    return boto3.client("s3", region_name=region, config=config)


def verifier_connexion_s3() -> dict[str, Any]:
    """Vérifie l'état de la connexion S3 et liste les informations du bucket."""
    bucket = obtenir_nom_bucket()
    region = os.environ.get("AWS_REGION") or "us-east-1"
    if not bucket:
        return {
            "connecte": False,
            "message": "Aucun bucket configuré (RDC_S3_BUCKET non défini dans .env)",
            "bucket": None,
            "region": region,
        }

    try:
        s3 = obtenir_client_s3(timeout_court=True)
        s3.head_bucket(Bucket=bucket)
        # Compter les objets
        prefixe = obtenir_prefixe_s3()
        reponse = s3.list_objects_v2(Bucket=bucket, Prefix=prefixe, MaxKeys=50)
        objets = reponse.get("Contents", [])
        return {
            "connecte": True,
            "message": "Connexion S3 opérationnelle",
            "bucket": bucket,
            "region": region,
            "prefixe": prefixe,
            "nb_objets_trouves": len(objets),
            "exemples_cles": [o["Key"] for o in objets[:5]],
        }
    except Exception as e:
        return {
            "connecte": False,
            "message": f"Erreur de connexion S3 : {type(e).__name__} ({e})",
            "bucket": bucket,
            "region": region,
        }


def sauvegarder_json_s3(cle: str, donnees: dict | list, bucket: str | None = None) -> bool:
    """Enregistre un dictionnaire ou une liste en JSON directement dans S3."""
    cible = bucket or obtenir_nom_bucket()
    if not cible:
        return False
    try:
        s3 = obtenir_client_s3()
        contenu = json.dumps(donnees, ensure_ascii=False, indent=2).encode("utf-8")
        s3.put_object(
            Bucket=cible,
            Key=cle,
            Body=contenu,
            ContentType="application/json; charset=utf-8",
        )
        return True
    except Exception as e:
        print(f"[s3_service] Erreur lors de l'enregistrement de {cle} sur S3: {e}")
        return False


def lire_json_s3(cle: str, bucket: str | None = None) -> dict | list | None:
    """Lit un fichier JSON directement depuis S3."""
    cible = bucket or obtenir_nom_bucket()
    if not cible:
        return None
    try:
        s3 = obtenir_client_s3()
        objet = s3.get_object(Bucket=cible, Key=cle)
        return json.loads(objet["Body"].read().decode("utf-8"))
    except Exception as e:
        return None


def televerser_fichier_s3(chemin_local: Path, cle_s3: str, bucket: str | None = None) -> bool:
    """Téléverse un fichier local (CSV, Parquet, JSON, etc.) vers S3."""
    cible = bucket or obtenir_nom_bucket()
    if not cible or not chemin_local.exists():
        return False
    try:
        s3 = obtenir_client_s3()
        content_type = "application/octet-stream"
        if chemin_local.suffix == ".json":
            content_type = "application/json"
        elif chemin_local.suffix == ".csv":
            content_type = "text/csv"
        elif chemin_local.suffix == ".parquet":
            content_type = "application/vnd.apache.parquet"

        with open(chemin_local, "rb") as f:
            s3.put_object(
                Bucket=cible,
                Key=cle_s3,
                Body=f.read(),
                ContentType=content_type,
            )
        return True
    except Exception as e:
        print(f"[s3_service] Échec upload {chemin_local} -> s3://{cible}/{cle_s3}: {e}")
        return False


def synchroniser_dossier_s3(dossier_local: Path, prefixe_s3: str, bucket: str | None = None) -> int:
    """Synchronise récursivement un dossier local vers un préfixe S3."""
    cible = bucket or obtenir_nom_bucket()
    if not cible or not dossier_local.exists():
        return 0

    reussis = 0
    for chemin in dossier_local.rglob("*"):
        if chemin.is_file():
            rel = chemin.relative_to(dossier_local).as_posix()
            cle = f"{prefixe_s3.rstrip('/')}/{rel}"
            if televerser_fichier_s3(chemin, cle, cible):
                reussis += 1
    return reussis
