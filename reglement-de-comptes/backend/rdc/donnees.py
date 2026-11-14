"""Chargement et préparation des données de départ.

Traitements appliqués (à reprendre dans la documentation technique) :
- prix utilisés : `adj_close` (ajusté pour dividendes et fractionnements) ;
- calendrier : jours ouvrables du lundi au vendredi ; un prix manquant (jour férié
  d'un seul marché) est remplacé par le dernier prix connu, 5 jours au maximum ;
  les variations de fin de semaine des cryptoactifs sont donc comptées le lundi ;
- devise : tout est converti en dollars canadiens avec le taux USD/CAD de la
  Banque du Canada, reporté du dernier jour connu les jours fériés canadiens.
"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent


def dossier_donnees() -> Path:
    """Dossier du jeu de départ : variable RDC_DATA_DIR, dossier local data/, sinon Datathon2026."""
    env = os.environ.get("RDC_DATA_DIR")
    if env and Path(env).exists():
        return Path(env)
    local_data = RACINE.parent / "data"
    if local_data.exists():
        return local_data
    return RACINE.parent.parent / "Datathon2026" / "alphaforge_starter"


def lire_csv(nom: str) -> pd.DataFrame:
    """Lit un CSV depuis S3 si RDC_S3_BUCKET est défini, sinon depuis le disque."""
    bucket = os.environ.get("RDC_S3_BUCKET")
    if bucket:
        import boto3  # importé ici pour que le mode local n'exige pas AWS

        prefixe = os.environ.get("RDC_S3_PREFIX", "")
        region = os.environ.get("AWS_REGION") or "us-east-1"
        objet = boto3.client("s3", region_name=region).get_object(Bucket=bucket, Key=f"{prefixe}{nom}")
        return pd.read_csv(io.BytesIO(objet["Body"].read()))
    return pd.read_csv(dossier_donnees() / nom)


@dataclass(frozen=True)
class Donnees:
    univers: pd.DataFrame      # index : ticker
    prix_cad: pd.DataFrame     # dates × tickers, en CAD
    rendements: pd.DataFrame   # rendements quotidiens simples, en CAD
    debut: str
    fin: str

    def source(self) -> str:
        return (
            "prices_daily.csv (Yahoo Finance via yfinance, extraction 2026-11-13), "
            "fx_usdcad_daily.csv (Banque du Canada), convertis en CAD"
        )


@lru_cache(maxsize=1)
def charger() -> Donnees:
    univers = lire_csv("assets_universe.csv").set_index("ticker")
    prix = lire_csv("prices_daily.csv", )
    fx = lire_csv("fx_usdcad_daily.csv")

    prix["date"] = pd.to_datetime(prix["date"])
    fx["date"] = pd.to_datetime(fx["date"])

    large = prix.pivot(index="date", columns="ticker", values="adj_close").sort_index()
    large = large[large.index.dayofweek < 5]           # lundi à vendredi
    large = large.ffill(limit=5)

    usdcad = fx.set_index("date")["usdcad"].sort_index().reindex(large.index).ffill().bfill()
    en_usd = [t for t in large.columns if univers.loc[t, "currency"] == "USD"]
    large[en_usd] = large[en_usd].mul(usdcad, axis=0)

    large = large.dropna(how="any")
    rendements = large.pct_change().dropna(how="any")
    return Donnees(
        univers=univers,
        prix_cad=large,
        rendements=rendements,
        debut=str(rendements.index[0].date()),
        fin=str(rendements.index[-1].date()),
    )


def load_market_data() -> Donnees:
    """Charge les données de marché (prix, univers, rendements en CAD).
    
    Conforme à l'Issue 1.1 de la Roadmap (chargement hybride S3/local avec cache).
    """
    return charger()


@lru_cache(maxsize=1)
def charger_macro() -> pd.DataFrame:
    macro = lire_csv("macro_rates.csv")
    macro["date"] = pd.to_datetime(macro["date"])
    return macro.sort_values("date")


def valeur_macro(serie: str, date: str, delai_publication_jours: int = 0) -> tuple[float, str] | None:
    """Dernière valeur connue de `serie` à `date`.

    Pour les séries mensuelles (IPC, chômage), passer un délai de publication : la valeur
    d'un mois de référence n'est connue que plusieurs semaines plus tard. On n'utilise donc
    que les observations dont la date de référence précède `date` d'au moins ce délai.
    """
    macro = charger_macro()
    limite = pd.Timestamp(date) - pd.Timedelta(days=delai_publication_jours)
    s = macro[(macro["series_id"] == serie) & (macro["date"] <= limite)]
    if s.empty:
        return None
    derniere = s.iloc[-1]
    return float(derniere["value"]), str(derniere["date"].date())


@lru_cache(maxsize=1)
def _fx() -> pd.Series:
    fx = lire_csv("fx_usdcad_daily.csv")
    fx["date"] = pd.to_datetime(fx["date"])
    return fx.set_index("date")["usdcad"].sort_index()


def valeur_fx(date: str) -> float | None:
    s = _fx().loc[:pd.Timestamp(date)]
    return float(s.iloc[-1]) if len(s) else None
