"""API du tribunal : expose le moteur Python à l'interface Angular et aux clients REST.

Lancer depuis le dossier du projet :
    uvicorn api:app --app-dir backend --port 8000

Aucun calcul direct ici : l'API appelle rdc (moteur, témoins, agents, greffier, règle,
intention, comparaison, scenarios, rapport_pdf) et renvoie le résultat au format JSON ou PDF.
"""
from __future__ import annotations

import os
from dataclasses import asdict
from typing import Literal

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from rdc import donnees, temoins, greffier
from rdc.profils import PROFILS
from rdc.proces import TAILLES_COURBE, courbe, ouvrir_proces, construire_dossier, regle_verdict
from rdc.intention import interpreter_intention
from rdc.comparaison import comparer_decision
from rdc.scenarios import generer_scenarios_alternatifs
from rdc.rapport_pdf import generer_pdf_rapport

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
    intention_texte: str | None = Field(default=None, description="Volonté de l'investisseur exprimée en texte libre")


class DemandeIntention(BaseModel):
    profil: str = Field(description="Clé du profil : amira, mateo ou robert")
    texte: str = Field(description="Demande en langage naturel (ex: devrais acheter +30% dans des etf ?)")


class DemandeComparaison(BaseModel):
    profil: str = Field(description="Clé du profil : amira, mateo ou robert")
    ticker: str = Field(description="Titre de l'univers")
    taille: float = Field(gt=0, le=0.5, description="Taille de la position")
    choix_investisseur: Literal["OUI", "NON"] = Field(description="Choix de l'investisseur face au verdict")


class DemandeScenarios(BaseModel):
    profil: str = Field(description="Clé du profil : amira, mateo ou robert")
    ticker: str = Field(description="Titre de la demande initiale")
    taille: float = Field(gt=0, le=0.5, description="Taille de la position initiale")
    intention_texte: str | None = Field(default=None, description="Intention textuelle initiale")


class DemandePDF(BaseModel):
    profil: str = Field(description="Clé du profil : amira, mateo ou robert")
    ticker: str = Field(description="Titre évalué")
    taille: float = Field(gt=0, le=0.5, description="Taille de l'allocation")
    mode: Literal["gabarit", "bedrock"] = "gabarit"
    intention_texte: str | None = None
    choix_investisseur: str | None = None


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


@app.post("/api/intention")
def interpreter_demande(demande: DemandeIntention) -> dict:
    profil = PROFILS.get(demande.profil)
    if profil is None:
        raise HTTPException(status_code=404, detail=f"Profil inconnu : {demande.profil}")
    d = _donnees()
    ticker, taille, explication = interpreter_intention(demande.texte, d.univers, profil)
    return {
        "ticker": ticker,
        "taille": taille,
        "nomTitre": str(d.univers.loc[ticker, "name"]),
        "classe": str(d.univers.loc[ticker, "asset_class"]),
        "explication": explication,
    }


@app.post("/api/proces")
def proces(demande: DemandeProces) -> dict:
    profil = PROFILS.get(demande.profil)
    if profil is None:
        raise HTTPException(status_code=404, detail=f"Profil inconnu : {demande.profil}")
    d = _donnees()
    if demande.ticker not in d.univers.index:
        raise HTTPException(status_code=404, detail=f"{demande.ticker} n'est pas dans l'univers de 31 actifs.")

    # Fonction synchrone : FastAPI l'exécute dans un thread pool
    p = ouvrir_proces(profil, demande.ticker, demande.taille, demande.mode,
                      intention_texte=demande.intention_texte or "")
    dossier = p.dossier
    table = courbe(dossier)
    rapport_explicabilite = greffier.generer_rapport_explicabilite(p)

    return {
        "demande": {
            "profil": profil.cle,
            "nom": profil.nom,
            "ticker": dossier.ticker,
            "nomTitre": str(d.univers.loc[dossier.ticker, "name"]),
            "taille": dossier.taille,
            "capital": profil.capital,
            "intention_texte": demande.intention_texte or "",
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
        "rapport_explicabilite": rapport_explicabilite,
    }


@app.post("/api/comparaison")
def comparer(demande: DemandeComparaison) -> dict:
    profil = PROFILS.get(demande.profil)
    if profil is None:
        raise HTTPException(status_code=404, detail=f"Profil inconnu : {demande.profil}")
    d = _donnees()
    if demande.ticker not in d.univers.index:
        raise HTTPException(status_code=404, detail=f"{demande.ticker} n'est pas dans l'univers de 31 actifs.")

    dossier = construire_dossier(profil, demande.ticker, demande.taille)
    decision = regle_verdict(dossier)
    choix_bool = demande.choix_investisseur == "OUI"
    comp = comparer_decision(dossier, decision, choix_bool)
    return asdict(comp)


@app.post("/api/scenarios")
def scenarios(demande: DemandeScenarios) -> list[dict]:
    profil = PROFILS.get(demande.profil)
    if profil is None:
        raise HTTPException(status_code=404, detail=f"Profil inconnu : {demande.profil}")
    d = _donnees()
    if demande.ticker not in d.univers.index:
        raise HTTPException(status_code=404, detail=f"{demande.ticker} n'est pas dans l'univers de 31 actifs.")

    dossier = construire_dossier(profil, demande.ticker, demande.taille)
    decision = regle_verdict(dossier)
    return generer_scenarios_alternatifs(dossier, decision, demande.intention_texte or "")


@app.post("/api/pdf")
def telecharger_pdf(demande: DemandePDF) -> Response:
    profil = PROFILS.get(demande.profil)
    if profil is None:
        raise HTTPException(status_code=404, detail=f"Profil inconnu : {demande.profil}")
    d = _donnees()
    if demande.ticker not in d.univers.index:
        raise HTTPException(status_code=404, detail=f"{demande.ticker} n'est pas dans l'univers de 31 actifs.")

    p = ouvrir_proces(profil, demande.ticker, demande.taille, demande.mode,
                      intention_texte=demande.intention_texte or "")
    
    scenarios_list = generer_scenarios_alternatifs(p.dossier, p.decision, demande.intention_texte or "")
    choix_bool = True if demande.choix_investisseur == "OUI" else (False if demande.choix_investisseur == "NON" else None)
    
    pdf_bytes = generer_pdf_rapport(
        proces=p,
        decision_investisseur=choix_bool,
        scenarios_alternatifs=scenarios_list,
        intention_texte=demande.intention_texte or "",
    )

    nom_fichier = f"jugement_tribunal_{profil.cle}_{demande.ticker}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nom_fichier}"'},
    )
