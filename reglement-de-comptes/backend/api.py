"""API du tribunal : expose le moteur Python à l'interface Angular et aux clients REST.

Lancer depuis le dossier du projet :
    uvicorn api:app --app-dir backend --port 8000

Aucun calcul direct ici : l'API appelle rdc (moteur, témoins, agents, greffier, règle,
intention, comparaison, scenarios, rapport_pdf) et renvoie le résultat au format JSON ou PDF.
"""
from __future__ import annotations

import json
import os
from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field, StringConstraints, model_validator

from rdc import donnees, greffier, questions, temoins
from rdc.profils import PROFILS, Profil
from rdc.proces import (TAILLES_COURBE, courbe, ouvrir_proces, construire_dossier, regle_verdict,
                        construire_timeline_discussion)
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
    profil: str = Field(description="Clé du profil : amira, mateo, robert ou personnalise")
    ticker: str = Field(description="Titre de l'univers de 31 actifs, par exemple NVDA")
    taille: float = Field(gt=0, le=0.5, description="Part du portefeuille à placer, de 0,05 à 0,5")
    # Bedrock par défaut. « gabarit » (sans modèle) reste disponible pour les tests hors ligne.
    mode: Literal["gabarit", "bedrock"] = "bedrock"
    intention_texte: str | None = Field(default=None, description="Volonté de l'investisseur exprimée en texte libre")


class Question(BaseModel):
    texte: str = Field(max_length=500, description="La question telle que l'investisseur l'a écrite")
    profil: str = Field(description="Clé du profil : amira, mateo, robert ou personnalise")
    ticker: str | None = Field(default=None, description="Titre déjà connu d'un échange précédent")
    taille: float | None = Field(default=None, description="Part déjà connue d'un échange précédent")
    comparer: list[str] | None = Field(default=None, min_length=2, max_length=2,
                                       description="Deux titres (ou « MOY:<domaine> ») choisis à l'écran")
    historique: list[str] = Field(default_factory=list, max_length=20,
                                  description="Questions précédentes de l'investisseur, de la plus ancienne à la plus récente")
    action: Literal["catalogue", "choisir_deux"] | None = Field(
        default=None, description="Bouton de l'écran : voir tous les titres, ou en choisir deux à comparer")


class CoteDuel(BaseModel):
    ticker: str
    taille: float = Field(gt=0, le=0.5)


class DemandeDuel(BaseModel):
    profil: str = Field(description="Clé du profil : amira, mateo, robert ou personnalise")
    a: CoteDuel
    b: CoteDuel
    mode: Literal["gabarit", "bedrock"] = "bedrock"


class DemandeIntention(BaseModel):
    profil: str = Field(description="Clé du profil : amira, mateo, robert ou personnalise")
    texte: str = Field(description="Demande en langage naturel (ex: devrais acheter +30% dans des etf ?)")


class DemandeComparaison(BaseModel):
    profil: str = Field(description="Clé du profil : amira, mateo, robert ou personnalise")
    ticker: str = Field(description="Titre de l'univers")
    taille: float = Field(gt=0, le=0.5, description="Taille de la position")
    choix_investisseur: Literal["OUI", "NON"] = Field(description="Choix de l'investisseur face au verdict")


class DemandeScenarios(BaseModel):
    profil: str = Field(description="Clé du profil : amira, mateo, robert ou personnalise")
    ticker: str = Field(description="Titre de la demande initiale")
    taille: float = Field(gt=0, le=0.5, description="Taille de la position initiale")
    intention_texte: str | None = Field(default=None, description="Intention textuelle initiale")


class DemandePDF(BaseModel):
    profil: str = Field(description="Clé du profil : amira, mateo, robert ou personnalise")
    ticker: str = Field(description="Titre évalué")
    taille: float = Field(gt=0, le=0.5, description="Taille de l'allocation")
    mode: Literal["gabarit", "bedrock"] = "bedrock"
    intention_texte: str | None = None
    choix_investisseur: str | None = None


_RISQUES_PERSONA = {
    "faible": ("Faible", 0.08),
    "faible_a_modere": ("Faible à modéré", 0.12),
    "modere": ("Modéré", 0.25),
    "modere_a_eleve": ("Modéré à élevé", 0.35),
    "eleve": ("Élevé", 0.45),
}


class PersonaPersonnalise(BaseModel):
    nom: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    age: int = Field(ge=1, le=120)
    risque: Literal["faible", "faible_a_modere", "modere", "modere_a_eleve", "eleve"]
    horizon_min: int = Field(ge=1, le=100)
    horizon_max: int = Field(ge=1, le=100)
    note: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def verifier_horizon(self) -> PersonaPersonnalise:
        if self.horizon_min > self.horizon_max:
            raise ValueError("L’horizon maximal doit être au moins égal à l’horizon minimal.")
        return self

    def creer_profil(self) -> Profil:
        # Capital, diversification et plafonds fictifs communs à toutes les simulations personnalisées.
        risque, budget = _RISQUES_PERSONA[self.risque]
        horizon = (f"{self.horizon_min} ans" if self.horizon_min == self.horizon_max
                   else f"{self.horizon_min} à {self.horizon_max} ans")
        return Profil(
            cle="personnalise",
            nom=self.nom,
            resume=f"{self.age} ans · Risque : {risque.lower()} · Horizon de {horizon}",
            objectif="Investir selon son horizon et sa tolérance aux pertes.",
            capital=100_000,
            horizon_ans=self.horizon_min,
            budget_perte=budget,
            plafond_position=0.20,
            plafond_secteur=0.40,
            preferences=self.note.strip(),
            portefeuille={"XIU.TO": 35, "SPY": 25, "XBB.TO": 40},
            horizon_max_declare=self.horizon_max,
            risque_declare=risque.lower(),
        )


_COOKIE_PERSONA = "rdc_persona"


def _persona_personnalise(request: Request) -> PersonaPersonnalise | None:
    cookie = request.cookies.get(_COOKIE_PERSONA)
    if not cookie:
        return None
    try:
        donnees_cookie = json.loads(urlsafe_b64decode(cookie))
        if isinstance(donnees_cookie, dict) and isinstance(donnees_cookie.get("horizon"), int):
            horizon = donnees_cookie.pop("horizon")
            pourcentage = donnees_cookie.get("risque")
            if isinstance(pourcentage, int):
                donnees_cookie.update(
                    horizon_min=horizon,
                    horizon_max=horizon,
                    risque=min(_RISQUES_PERSONA, key=lambda niveau: abs(_RISQUES_PERSONA[niveau][1] * 100 - pourcentage)),
                )
        return PersonaPersonnalise.model_validate(donnees_cookie)
    except ValueError:
        return None


def _profil(request: Request, cle: str) -> Profil:
    if cle == "personnalise":
        persona = _persona_personnalise(request)
        if persona is not None:
            return persona.creer_profil()
    profil = PROFILS.get(cle)
    if profil is None:
        raise HTTPException(status_code=404, detail=f"Profil inconnu : {cle}")
    return profil


def _source() -> dict:
    from rdc import s3_service
    etat_s3 = s3_service.verifier_connexion_s3()
    return {
        "type": "s3" if etat_s3.get("connecte") else "local",
        "s3": etat_s3,
        "bucket": etat_s3.get("bucket"),
        "region": etat_s3.get("region", "us-east-1"),
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


def _dossier_investisseur(p, univers) -> dict:
    """Le dossier complet d'un persona, pour l'archiviste (« qu'est-ce que j'ai dans mon portefeuille ? »)."""
    total = sum(p.portefeuille.values())
    return {
        "cle": p.cle, "nom": p.nom, "resume": p.resume, "objectif": p.objectif,
        "preferences": p.preferences, "capital": p.capital, "horizonAns": p.horizon_ans,
        "budgetPerte": p.budget_perte, "plafondPosition": p.plafond_position,
        "plafondSecteur": p.plafond_secteur, "classesExclues": list(p.classes_exclues),
        "filtreEsg": p.filtre_esg, "secteursAJustifier": list(p.secteurs_a_justifier),
        "portefeuille": [{"ticker": t, "nomTitre": str(univers.loc[t, "name"]) if t in univers.index else t,
                          "classe": str(univers.loc[t, "asset_class"]) if t in univers.index else "",
                          "poids": v / total} for t, v in p.portefeuille.items()],
    }


def _profil_public(p: Profil) -> dict:
    total = sum(p.portefeuille.values())
    return {
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
    }


@app.get("/api/profils")
def profils(request: Request, response: Response) -> list[dict]:
    response.headers["Cache-Control"] = "private, no-store"
    personnalise = _persona_personnalise(request)
    resultat = [_profil_public(p) for p in PROFILS.values()]
    if personnalise is not None:
        resultat.append({**_profil_public(personnalise.creer_profil()), "configuration": personnalise.model_dump()})
    return resultat


@app.post("/api/profils/personnalise")
def enregistrer_persona(persona: PersonaPersonnalise, request: Request, response: Response) -> dict:
    cookie = urlsafe_b64encode(persona.model_dump_json().encode()).decode("ascii")
    response.set_cookie(_COOKIE_PERSONA, cookie, httponly=True, samesite="lax",
                        secure=request.url.scheme == "https")
    return {**_profil_public(persona.creer_profil()), "configuration": persona.model_dump()}


@app.get("/api/actifs")
def actifs() -> list[dict]:
    univers = _donnees().univers
    return [{"ticker": t, "nom": str(univers.loc[t, "name"]), "classe": str(univers.loc[t, "asset_class"])}
            for t in univers.index]


@app.get("/api/tailles")
def tailles() -> list[float]:
    return [t for t in TAILLES_COURBE if t > 0]


@app.post("/api/questions/analyser")
def analyser_question(q: Question, request: Request) -> dict:
    """Le greffier dit si la question peut être jugée, et sinon pourquoi."""
    profil = _profil(request, q.profil)
    univers = {t: str(n) for t, n in _donnees().univers["name"].items()}
    if q.action:
        # Boutons « Voir tous les titres » et « Comparer deux titres » : l'archiviste montre le catalogue.
        from rdc import archiviste
        r = archiviste.catalogue(set(profil.portefeuille), set(profil.classes_exclues))
        if q.action == "catalogue":
            return questions.Analyse("catalogue", "catalogue", r["message"], agent="archiviste",
                                     groupes=r["groupes"]).en_json()
        s = archiviste.selection(r["groupes"], un_par_groupe=False)
        return questions.Analyse("selection", "selection", "Choisissez deux titres à mettre côte à côte.",
                                 agent="archiviste", groupes=s["groupes"], selection="deux").en_json()
    if q.comparer:
        # Comparaison choisie à l'écran (titres ou moyennes de domaine) : l'archiviste répond directement.
        from rdc import archiviste
        a, b = q.comparer
        try:
            r = archiviste.comparer(a, b)
        except KeyError as erreur:
            raise HTTPException(status_code=404, detail=f"Inconnu : {erreur}") from erreur
        choix = [questions.Choix(t, univers[t], questions.part_par_defaut(t),
                                 questions.formuler(t, questions.part_par_defaut(t), univers),
                                 "Soumettre ce titre au tribunal") for t in (a, b) if t in univers]
        return questions.Analyse("comparaison", "comparaison", r["message"], agent="archiviste",
                                 fiches=r["fiches"], choix=choix).en_json()
    ticker = q.ticker if q.ticker in univers else None
    analyse = questions.analyser(q.texte, univers, ticker, q.taille, titre_exemple=profil.demande_exemple[0],
                                 resume_profil=f"{profil.nom}, {profil.resume} {profil.preferences}",
                                 portefeuille=set(profil.portefeuille), classes_exclues=set(profil.classes_exclues),
                                 historique=[h[:500] for h in q.historique],
                                 profil_info=_dossier_investisseur(profil, _donnees().univers))
    return analyse.en_json()


@app.get("/api/actions")
def liste_actions() -> list[dict]:
    """Retourne la synthèse financière précalculée de chaque action pour les agents et le frontend."""
    from rdc import actions_store
    df = actions_store.obtenir_resume_catalogue()
    if df.empty:
        return []
    return df.to_dict(orient="records")


@app.get("/api/actions/{ticker}")
def detail_action(ticker: str) -> dict:
    """Retourne la fiche d'analyse quantitative complète précalculée d'une action/titre."""
    from rdc import actions_store
    d = _donnees()
    ticker_clean = ticker.upper().strip()
    if ticker_clean not in d.univers.index:
        raise HTTPException(status_code=404, detail=f"Action '{ticker}' introuvable dans l'univers de 31 actifs.")
    return actions_store.obtenir_fiche_action(ticker_clean)


@app.post("/api/actions/extraire")
def declencher_extraction(televerser_s3: bool = True) -> dict:
    """Déclenche la ré-extraction et synchronisation S3 de toutes les fiches d'actifs."""
    from rdc import extraire_fiches_actions
    return extraire_fiches_actions.extraire_toutes_les_actions(televerser_s3=televerser_s3)


@app.post("/api/intention")
def interpreter_demande(demande: DemandeIntention, request: Request) -> dict:
    profil = _profil(request, demande.profil)
    d = _donnees()
    ticker, taille, explication = interpreter_intention(demande.texte, d.univers, profil)
    return {
        "ticker": ticker,
        "taille": taille,
        "nomTitre": str(d.univers.loc[ticker, "name"]),
        "classe": str(d.univers.loc[ticker, "asset_class"]),
        "explication": explication,
    }


@app.post("/api/duel")
def duel(demande: DemandeDuel, request: Request) -> dict:
    """Deux procès sur le même profil, puis une décision A contre B selon une règle fixe."""
    from rdc.duel import juger_duel
    profil = _profil(request, demande.profil)
    d = _donnees()
    for cote in (demande.a, demande.b):
        if cote.ticker not in d.univers.index:
            raise HTTPException(status_code=404, detail=f"{cote.ticker} n'est pas dans l'univers de 31 actifs.")
    if demande.a.ticker == demande.b.ticker:
        raise HTTPException(status_code=422, detail="Un duel oppose deux titres différents.")
    return juger_duel(profil, (demande.a.ticker, demande.a.taille), (demande.b.ticker, demande.b.taille),
                      demande.mode)


@app.post("/api/proces")
def proces(demande: DemandeProces, request: Request) -> dict:
    profil = _profil(request, demande.profil)
    d = _donnees()
    if demande.ticker not in d.univers.index:
        raise HTTPException(status_code=404, detail=f"{demande.ticker} n'est pas dans l'univers de 31 actifs.")

    # Fonction synchrone : FastAPI l'exécute dans un thread pool
    p = ouvrir_proces(profil, demande.ticker, demande.taille, demande.mode,
                      intention_texte=demande.intention_texte or "")
    dossier = p.dossier
    table = courbe(dossier)
    rapport_explicabilite = greffier.generer_rapport_explicabilite(p)
    discussion = construire_timeline_discussion(p)

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
        "discussion": discussion,
    }


@app.post("/api/proces/discussion")
def discussion_seule(demande: DemandeProces, request: Request) -> list[dict]:
    """Renvoie uniquement la chronologie théâtralisée du débat (tours de parole) pour affichage cadencé."""
    profil = _profil(request, demande.profil)
    d = _donnees()
    if demande.ticker not in d.univers.index:
        raise HTTPException(status_code=404, detail=f"{demande.ticker} n'est pas dans l'univers de 31 actifs.")

    p = ouvrir_proces(profil, demande.ticker, demande.taille, demande.mode,
                      intention_texte=demande.intention_texte or "")
    return construire_timeline_discussion(p)


@app.post("/api/proces/stream")
async def stream_proces(demande: DemandeProces, request: Request):
    """Diffusion en streaming (Server-Sent Events) cadencée des prises de parole du tribunal."""
    profil = _profil(request, demande.profil)
    d = _donnees()
    if demande.ticker not in d.univers.index:
        raise HTTPException(status_code=404, detail=f"{demande.ticker} n'est pas dans l'univers de 31 actifs.")

    import asyncio
    import json
    from fastapi.responses import StreamingResponse

    p = ouvrir_proces(profil, demande.ticker, demande.taille, demande.mode,
                      intention_texte=demande.intention_texte or "")
    timeline = construire_timeline_discussion(p)

    async def event_generator():
        for tour in timeline:
            yield f"data: {json.dumps(tour, ensure_ascii=False)}\n\n"
            pause_sec = tour.get("pause_ms", 2500) / 1000.0
            await asyncio.sleep(pause_sec)
        yield "event: end\ndata: {}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/comparaison")
def comparer(demande: DemandeComparaison, request: Request) -> dict:
    profil = _profil(request, demande.profil)
    d = _donnees()
    if demande.ticker not in d.univers.index:
        raise HTTPException(status_code=404, detail=f"{demande.ticker} n'est pas dans l'univers de 31 actifs.")

    dossier = construire_dossier(profil, demande.ticker, demande.taille)
    decision = regle_verdict(dossier)
    choix_bool = demande.choix_investisseur == "OUI"
    comp = comparer_decision(dossier, decision, choix_bool)
    return asdict(comp)


@app.post("/api/scenarios")
def scenarios(demande: DemandeScenarios, request: Request) -> list[dict]:
    profil = _profil(request, demande.profil)
    d = _donnees()
    if demande.ticker not in d.univers.index:
        raise HTTPException(status_code=404, detail=f"{demande.ticker} n'est pas dans l'univers de 31 actifs.")

    dossier = construire_dossier(profil, demande.ticker, demande.taille)
    decision = regle_verdict(dossier)
    return generer_scenarios_alternatifs(dossier, decision, demande.intention_texte or "")


@app.post("/api/pdf")
def telecharger_pdf(demande: DemandePDF, request: Request) -> Response:
    profil = _profil(request, demande.profil)
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
