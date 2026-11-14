"""API du tribunal : expose le moteur Python à l'interface Angular.

Lancer depuis le dossier du projet :
    uvicorn api:app --app-dir backend --port 8000

Aucun calcul ici : l'API appelle rdc (moteur, témoins, agents, greffier, règle)
et met le résultat en JSON.
"""
from __future__ import annotations

import os
from dataclasses import asdict
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from rdc import donnees, temoins
from rdc.profils import PROFILS
from rdc.proces import TAILLES_COURBE, courbe, ouvrir_proces

app = FastAPI(
    title="Règlement de comptes",
    description="Tribunal financier simulé. Simulation pédagogique, pas un conseil financier.",
    root_path=os.environ.get("RDC_API_ROOT_PATH", ""),
)


class DemandeProces(BaseModel):
    profil: str = Field(description="Clé du profil : amira, mateo ou robert")
    ticker: str = Field(description="Titre de l'univers de 31 actifs, par exemple NVDA")
    taille: float = Field(gt=0, le=0.5, description="Part du portefeuille à placer, de 0,05 à 0,5")
    mode: Literal["gabarit", "bedrock"] = "gabarit"


def _source() -> dict:
    bucket = os.environ.get("RDC_S3_BUCKET")
    return {
        "type": "s3" if bucket else "local",
        "bucket": bucket,
        "region": os.environ.get("AWS_REGION") or "us-east-1",
    }


def _donnees():
    try:
        return donnees.charger()
    except Exception as erreur:  # fichier absent, identifiants AWS absents ou expirés, bucket introuvable
        source = _source()
        if source["type"] == "s3":
            detail = (f"Lecture impossible dans S3 (bucket {source['bucket']}) : "
                      f"{type(erreur).__name__} : {erreur}. Collez des identifiants récents depuis "
                      "« Get AWS CLI credentials » dans Workshop Studio.")
        else:
            detail = ("Données introuvables. Définissez RDC_DATA_DIR vers le dossier "
                      f"alphaforge_starter. Détail : {erreur}")
        raise HTTPException(status_code=503, detail=detail) from erreur


@app.get("/api/sante")
def sante() -> dict:
    d = _donnees()
    return {"source": _source(), "periode": {"debut": d.debut, "fin": d.fin}}


@app.get("/api/profils")
def profils() -> list[dict]:
    resultat = []
    for p in PROFILS.values():
        total = sum(p.portefeuille.values())
        resultat.append({
            "cle": p.cle,
            "nom": p.nom,
            "resume": p.resume,
            "objectif": p.objectif,
            "preferences": p.preferences,
            "capital": p.capital,
            "horizonAns": p.horizon_ans,
            "budgetPerte": p.budget_perte,
            "plafondPosition": p.plafond_position,
            "portefeuille": [{"ticker": t, "poids": v / total} for t, v in p.portefeuille.items()],
            "demandeExemple": {"ticker": p.demande_exemple[0], "taille": p.demande_exemple[1]},
        })
    return resultat


@app.get("/api/actifs")
def actifs() -> list[dict]:
    univers = _donnees().univers
    return [{"ticker": t, "nom": str(univers.loc[t, "name"]), "classe": str(univers.loc[t, "asset_class"])}
            for t in univers.index]


@app.get("/api/tailles")
def tailles() -> list[float]:
    return [t for t in TAILLES_COURBE if t > 0]


@app.post("/api/proces")
def proces(demande: DemandeProces) -> dict:
    profil = PROFILS.get(demande.profil)
    if profil is None:
        raise HTTPException(status_code=404, detail=f"Profil inconnu : {demande.profil}")
    d = _donnees()
    if demande.ticker not in d.univers.index:
        raise HTTPException(status_code=404, detail=f"{demande.ticker} n'est pas dans l'univers de 31 actifs.")

    # Fonction synchrone : FastAPI l'exécute dans un fil séparé (un procès Bedrock dure ~30 s).
    p = ouvrir_proces(profil, demande.ticker, demande.taille, demande.mode)
    dossier = p.dossier
    table = courbe(dossier)
    return {
        "demande": {
            "profil": profil.cle,
            "nom": profil.nom,
            "ticker": dossier.ticker,
            "nomTitre": str(d.univers.loc[dossier.ticker, "name"]),
            "taille": dossier.taille,
            "capital": profil.capital,
        },
        "periode": {"debut": dossier.debut, "fin": dossier.fin},
        "mode": p.mode,
        "avertissement": p.avertissement,
        "decision": p.decision,
        "plaidoiries": [asdict(x) for x in p.plaidoiries],
        "motivation": asdict(p.motivation),
        "salle": p.salle,
        "courbe": [
            {
                "taille": float(r["taille"]),
                "pireBaisse": float(r["pire_baisse"]),
                "defavorable12Mois": float(r["defavorable_5pct_12_mois"]),
                "partDuRisque": float(r["part_du_risque_du_titre"]),
            }
            for _, r in table.iterrows()
        ],
        "budgetPerte": -profil.budget_perte,
        "pieces": [
            {
                "numero": piece.numero,
                "temoin": piece.temoin,
                "description": temoins.DESCRIPTIONS[piece.temoin],
                "outil": piece.outil,
                "appelePar": piece.appele_par,
                "horodatage": piece.horodatage,
                "faits": [{"libelle": k, "valeur": v} for k, v in piece.faits.items()],
                "source": piece.source,
                "periode": piece.periode,
                "limites": piece.limites,
            }
            for piece in p.greffier.pieces
        ],
    }
