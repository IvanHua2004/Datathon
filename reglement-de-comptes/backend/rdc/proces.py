"""Le déroulement du procès : dossier, règle de verdict, salle.

Le verdict est décidé par une RÈGLE déterministe, pas par un modèle de langage.
Le juge (agent) ne fait que le motiver à partir des pièces.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import donnees as dn
from . import moteur, temoins
from .format import annees, pct
from .greffier import Greffier
from .profils import Profil

SEUIL_PART_RISQUE = 0.50        # hypothèse de l'équipe : une position ne devrait pas porter
                                # plus de la moitié du risque total sans que ce soit signalé
TAILLES_COURBE = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]

V_CONTRAINTE = "Contraire à une contrainte déclarée"
V_TENSION = "En tension avec le profil déclaré"
V_INDECIDABLE = "Indécidable : information manquante"
V_COMPATIBLE = "Compatible avec le profil déclaré"


@dataclass
class Dossier:
    profil: Profil
    ticker: str
    taille: float
    donnees: dn.Donnees
    debut: str
    fin: str
    avant: dict
    apres: dict
    crise: dict
    titre_seul: dict
    secteur: str
    classe_actif: str
    preuves_esg: pd.DataFrame


def construire_dossier(profil: Profil, ticker: str, taille: float,
                       rend: pd.DataFrame | None = None) -> Dossier:
    d = dn.charger()
    if ticker not in d.univers.index:
        raise KeyError(f"{ticker} n'est pas dans l'univers de 31 actifs.")
    rend = d.rendements if rend is None else rend
    poids_apres = moteur.ajouter_position(profil.portefeuille, ticker, taille)
    return Dossier(
        profil=profil, ticker=ticker, taille=taille, donnees=d,
        debut=str(rend.index[0].date()), fin=str(rend.index[-1].date()),
        avant=moteur.resume(rend, d.univers, profil.portefeuille),
        apres=moteur.resume(rend, d.univers, poids_apres),
        crise=moteur.comportement_en_crise(rend, profil.portefeuille, ticker),
        titre_seul=moteur.pire_baisse(rend[ticker]),
        secteur=str(d.univers.loc[ticker, "sector"]),
        classe_actif=str(d.univers.loc[ticker, "asset_class"]),
        preuves_esg=temoins.lire_preuves_esg(ticker),
    )


def regle_verdict(dossier: Dossier) -> dict:
    """Applique les contraintes (limites dures) puis les tensions. Retourne verdict et motifs."""
    p, t, ap = dossier.profil, dossier.ticker, dossier.apres
    contraintes, tensions, manquants = [], [], []

    if dossier.classe_actif in p.classes_exclues:
        contraintes.append({"temoin": "diversification",
                            "texte": f"{t} appartient à une classe d'actifs exclue par le profil ({dossier.classe_actif})."})
    poids_titre = ap["poids"].get(t, 0.0)
    if dossier.classe_actif in ("equity", "crypto") and poids_titre > p.plafond_position:
        contraintes.append({"temoin": "risque",
                            "texte": f"{t} pèserait {pct(poids_titre)} du portefeuille, au-dessus du plafond "
                                     f"de {pct(p.plafond_position)} par titre individuel."})
    if p.filtre_esg and not dossier.preuves_esg.empty:
        exclusions = dossier.preuves_esg[(dossier.preuves_esg["type"] == "exclusion")
                                         & (dossier.preuves_esg["nature"] == "fait_etabli")]
        if len(exclusions):
            contraintes.append({"temoin": "valeurs",
                                "texte": f"{len(exclusions)} fait(s) établi(s) classé(s) « exclusion » pour {t} dans la table de preuves ESG."})

    perte = -ap["pire_baisse"]["profondeur"]
    if perte > p.budget_perte:
        tensions.append({"temoin": "risque",
                         "texte": f"La pire baisse observée avec la position ({pct(-perte)}) dépasse le budget "
                                  f"de perte déclaré ({pct(-p.budget_perte)})."})
    duree = ap["pire_baisse"]["annees_sous_le_sommet"]
    if duree > p.horizon_ans:
        tensions.append({"temoin": "risque",
                         "texte": f"Le temps passé sous le sommet ({annees(duree)}) dépasse l'horizon de {annees(p.horizon_ans)}."})
    part = ap["contributions_risque"].get(t, 0.0)
    if part > SEUIL_PART_RISQUE:
        tensions.append({"temoin": "risque",
                         "texte": f"{t} porterait {pct(part)} du risque total pour {pct(poids_titre)} du portefeuille."})
    poids_secteur = ap["concentration"]["par_secteur"].get(dossier.secteur, 0.0)
    if poids_secteur > p.plafond_secteur:
        tensions.append({"temoin": "diversification",
                         "texte": f"Le secteur {dossier.secteur} atteindrait {pct(poids_secteur)}, au-dessus du plafond de {pct(p.plafond_secteur)}."})

    if p.filtre_esg and dossier.secteur in p.secteurs_a_justifier and dossier.preuves_esg.empty:
        manquants.append({"temoin": "valeurs",
                          "texte": f"Aucune preuve ESG n'a été collectée pour {t}, alors que le secteur "
                                   f"{dossier.secteur} doit être justifié pour ce profil."})

    if contraintes:
        verdict = V_CONTRAINTE
    elif tensions:
        verdict = V_TENSION
    elif manquants:
        verdict = V_INDECIDABLE
    else:
        verdict = V_COMPATIBLE
    return {"verdict": verdict, "contraintes": contraintes, "tensions": tensions, "manquants": manquants}


def salle(dossier: Dossier, verdict_de_reference: str) -> list[dict]:
    """La salle : on rejoue la règle en changeant UNE hypothèse à la fois."""
    p, t, taille = dossier.profil, dossier.ticker, dossier.taille
    rend = dossier.donnees.rendements
    sans_2022 = rend[rend.index.year != 2022]
    scenarios = [
        ("Position deux fois plus petite", p, taille / 2, None),
        ("Horizon deux fois plus long", p.avec(horizon_ans=p.horizon_ans * 2), taille, None),
        ("Budget de perte augmenté de 10 points", p.avec(budget_perte=p.budget_perte + 0.10), taille, None),
        ("Sans l'année 2022 dans les données", p, taille, sans_2022),
    ]
    resultat = []
    for nom, profil, tl, r in scenarios:
        v = regle_verdict(construire_dossier(profil, t, tl, r))["verdict"]
        resultat.append({"hypothese": nom, "verdict": v, "change": v != verdict_de_reference})
    return resultat


def courbe(dossier: Dossier) -> pd.DataFrame:
    lignes = moteur.courbe_taille(dossier.donnees.rendements, dossier.profil.portefeuille,
                                  dossier.ticker, TAILLES_COURBE)
    df = pd.DataFrame(lignes)
    df["budget_perte"] = -dossier.profil.budget_perte
    return df


@dataclass
class Proces:
    dossier: Dossier
    greffier: Greffier
    decision: dict
    plaidoiries: list = field(default_factory=list)   # liste de agents.Plaidoirie
    motivation: object = None                          # agents.Plaidoirie du juge
    salle: list = field(default_factory=list)
    mode: str = "gabarit"
    avertissement: str | None = None


def ouvrir_proces(profil: Profil, ticker: str, taille: float, mode: str = "gabarit") -> Proces:
    from . import agents            # import tardif : agents dépend de ce module

    dossier = construire_dossier(profil, ticker, taille)
    greffier = Greffier()
    greffier.admettre(profil.resume, f"{profil.capital:.0f}", pct(taille), pct(taille, 0),
                      pct(profil.budget_perte), pct(profil.plafond_position),
                      pct(profil.plafond_secteur), annees(profil.horizon_ans),
                      pct(SEUIL_PART_RISQUE, 0), "2022", "12", "5", "10")
    decision = regle_verdict(dossier)
    proces = Proces(dossier=dossier, greffier=greffier, decision=decision, mode=mode)
    proces.salle = salle(dossier, decision["verdict"])
    agents.plaider(proces)
    return proces
