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
    intention_texte: str = ""


def ouvrir_proces(profil: Profil, ticker: str, taille: float, mode: str = "gabarit",
                  intention_texte: str = "") -> Proces:
    from . import agents            # import tardif : agents dépend de ce module

    dossier = construire_dossier(profil, ticker, taille)
    greffier = Greffier()
    greffier.admettre(profil.resume, f"{profil.capital:.0f}", pct(taille), pct(taille, 0),
                      pct(profil.budget_perte), pct(profil.plafond_position),
                      pct(profil.plafond_secteur), annees(profil.horizon_ans),
                      pct(SEUIL_PART_RISQUE, 0), "2022", "12", "5", "10")
    decision = regle_verdict(dossier)
    proces = Proces(dossier=dossier, greffier=greffier, decision=decision, mode=mode,
                    intention_texte=intention_texte)
    proces.salle = salle(dossier, decision["verdict"])
    agents.plaider(proces)
    return proces


def lancer_proces_stream(profil: Profil, ticker: str, taille: float, mode: str = "gabarit",
                         intention_texte: str = ""):
    """Générateur de streaming du procès (avec yield) pour un affichage interactif direct.
    
    Conforme à l'Issue 3.1 de la Roadmap (effet machine à écrire / interaction continue).
    """
    from . import agents

    dossier = construire_dossier(profil, ticker, taille)
    greffier = Greffier()
    greffier.admettre(profil.resume, f"{profil.capital:.0f}", pct(taille), pct(taille, 0),
                      pct(profil.budget_perte), pct(profil.plafond_position),
                      pct(profil.plafond_secteur), annees(profil.horizon_ans),
                      pct(SEUIL_PART_RISQUE, 0), "2022", "12", "5", "10")
    decision = regle_verdict(dossier)
    proces = Proces(dossier=dossier, greffier=greffier, decision=decision, mode=mode,
                    intention_texte=intention_texte)
    proces.salle = salle(dossier, decision["verdict"])

    # Étape 1 : Ouverture solennelle par l'Huissier
    yield {
        "etape": "HUISSIER",
        "acteur": "L'Huissier d'audience",
        "titre": "Ouverture de la séance",
        "texte": (f"Silence dans la salle ! Le Tribunal d'AlphaForge entre en audience solennelle. "
                  f"Affaire en délibéré : l'investisseur {profil.nom} ({profil.resume}) soumet la volonté suivante : "
                  f"« {intention_texte or f'Allouer {pct(taille, 0)} dans {ticker}'} ». "
                  f"L'actif visé est {ticker} ({dossier.donnees.univers.loc[ticker, 'name']}). "
                  f"Que les témoins experts prêtent serment et déposent leurs pièces à conviction.")
    }

    # Étape 2 : Plaidoiries et convocation des témoins
    agents.plaider(proces)

    # Étape 3 : Déposition des témoins incarnés
    depositions = agents.depositions_temoins_incarnee(proces)
    for dep in depositions:
        yield {
            "etape": "TEMOIN",
            "acteur": dep["personnage"],
            "titre": f"Déposition sous serment — Pièce [{dep['piece']}]",
            "temoin": dep["temoin"],
            "piece": dep["piece"],
            "texte": dep["texte"]
        }

    # Étape 4 : Plaidoirie de la Défense (Me Vigor)
    defense = proces.plaidoiries[0]
    yield {
        "etape": "DEFENSE",
        "acteur": defense.role,
        "titre": "Plaidoirie en faveur de la demande",
        "texte": defense.texte,
        "convoques": defense.temoins_convoques,
        "non_verifies": defense.non_verifies
    }

    # Étape 5 : Réquisitoire du Procureur / Gouvernance (Me Austère)
    procureur = proces.plaidoiries[1]
    yield {
        "etape": "PROCUREUR",
        "acteur": procureur.role,
        "titre": "Réquisitoire de la Gouvernance et du Risque",
        "texte": procureur.texte,
        "convoques": procureur.temoins_convoques,
        "non_verifies": procureur.non_verifies
    }

    # Étape 6 : Verdict motivé du Président du Tribunal (Le Juge)
    juge = proces.motivation
    yield {
        "etape": "JUGE",
        "acteur": juge.role,
        "titre": f"Verdict officiel : {decision['verdict']}",
        "verdict": decision["verdict"],
        "texte": juge.texte,
        "proces": proces
    }


def construire_timeline_discussion(proces: Proces) -> list[dict]:
    """Construit la séquence chronologique du débat pour une restitution animée côté front.

    Permet à l'interface de dérouler une discussion vivante et cadencée entre :
    1. L'Huissier (ouverture de séance)
    2. Le Greffier (dépôt et scellé des pièces)
    3. Les Témoins experts sous serment (dépositions incarnées)
    4. L'Avocat de la Défense (Me Vigor - plaidoirie)
    5. Le Greffier (contrôle factuel de la défense)
    6. L'Autre Avocat / Le Procureur (Me Austère - réquisitoire)
    7. Le Greffier (contrôle factuel du procureur)
    8. Le Président du Tribunal (délibéré, verdict officiel et motivation)
    """
    from . import agents

    dossier = proces.dossier
    profil = dossier.profil
    timeline: list[dict] = []
    ordre = 1

    # 1. Ouverture solennelle par l'Huissier
    volonte = proces.intention_texte or f"Allouer {pct(dossier.taille, 0)} dans {dossier.ticker}"
    nom_titre = dossier.donnees.univers.loc[dossier.ticker, "name"] if dossier.ticker in dossier.donnees.univers.index else dossier.ticker
    timeline.append({
        "ordre": ordre,
        "etape": "HUISSIER_OUVERTURE",
        "acteur": "L'Huissier d'audience",
        "role": "huissier",
        "avatar": "📢",
        "titre": "Ouverture solennelle de la séance",
        "texte": (f"Silence dans la salle ! Le Tribunal d'AlphaForge entre en audience solennelle. "
                  f"Affaire en délibéré : l'investisseur {profil.nom} ({profil.resume}) soumet la volonté suivante : "
                  f"« {volonte} ». "
                  f"L'actif visé est {dossier.ticker} ({nom_titre}). "
                  f"Que les témoins experts prêtent serment et déposent leurs pièces à conviction."),
        "pause_ms": 2500,
    })
    ordre += 1

    # 2. Dépôt des pièces par le Greffier
    pieces_numeros = [p.numero for p in proces.greffier.pieces]
    pieces_resume = ", ".join(f"[{p.numero}] {p.temoin.capitalize()}" for p in proces.greffier.pieces)
    timeline.append({
        "ordre": ordre,
        "etape": "GREFFIER_DEPOT",
        "acteur": "Le Greffier d'audience",
        "role": "greffier",
        "avatar": "📜",
        "titre": "Enregistrement des pièces au greffe",
        "texte": (f"Monsieur le Président, j'enregistre officiellement {len(proces.greffier.pieces)} pièces à conviction "
                  f"au dossier de l'affaire : {pieces_resume}. "
                  f"Toutes les données ont été calculées et scellées sous contrôle du greffe."),
        "pieces_associees": pieces_numeros,
        "pause_ms": 2200,
    })
    ordre += 1

    # 3. Déposition des témoins incarnés
    depositions = agents.depositions_temoins_incarnee(proces)
    icones_temoins = {
        "risque": "📊",
        "diversification": "🧭",
        "valeurs": "🌱",
        "macro": "🏦",
    }
    for dep in depositions:
        timeline.append({
            "ordre": ordre,
            "etape": "TEMOIN",
            "acteur": dep["personnage"],
            "role": "temoin",
            "avatar": icones_temoins.get(dep["temoin"], "⚖️"),
            "titre": f"Déposition sous serment — Pièce [{dep['piece']}] ({dep['role']})",
            "temoin": dep["temoin"],
            "piece": dep["piece"],
            "texte": dep["texte"],
            "pause_ms": 3200,
        })
        ordre += 1

    # 4. Plaidoirie de la Défense (Me Vigor)
    defense = proces.plaidoiries[0] if proces.plaidoiries else None
    if defense:
        timeline.append({
            "ordre": ordre,
            "etape": "PLAIDOIRIE_DEFENSE",
            "acteur": defense.role,
            "role": "avocat_defense",
            "avatar": "💼",
            "titre": "Plaidoirie en faveur de la demande",
            "texte": defense.texte,
            "convoques": defense.temoins_convoques,
            "pause_ms": 3800,
        })
        ordre += 1

        # 5. Audit de la Défense par le Greffier
        non_v = defense.non_verifies
        texte_greffier = (f"⚠️ Alerte du Greffier : chiffres absents des pièces d'instruction cités par la Défense → {', '.join(non_v)}."
                          if non_v else "Contrôle du Greffier : tous les chiffres cités par Me Vigor sont strictement conformes aux pièces scellées.")
        timeline.append({
            "ordre": ordre,
            "etape": "AUDIT_GREFFIER_DEFENSE",
            "acteur": "Le Greffier d'audience",
            "role": "greffier",
            "avatar": "⚖️",
            "titre": "Contrôle factuel de la Défense",
            "texte": texte_greffier,
            "statut": "alerte" if non_v else "valide",
            "non_verifies": non_v,
            "pause_ms": 2000,
        })
        ordre += 1

    # 6. Réquisitoire du Procureur (Me Austère)
    procureur = proces.plaidoiries[1] if len(proces.plaidoiries) > 1 else None
    if procureur:
        timeline.append({
            "ordre": ordre,
            "etape": "REQUISITOIRE_PROCUREUR",
            "acteur": procureur.role,
            "role": "procureur",
            "avatar": "🛡️",
            "titre": "Réquisitoire de la Gouvernance et des Risques",
            "texte": procureur.texte,
            "convoques": procureur.temoins_convoques,
            "pause_ms": 4000,
        })
        ordre += 1

        # 7. Audit du Procureur par le Greffier
        non_v_p = procureur.non_verifies
        texte_greffier_p = (f"⚠️ Alerte du Greffier : chiffres absents des pièces cités par le Procureur → {', '.join(non_v_p)}."
                            if non_v_p else "Contrôle du Greffier : les objections du Procureur s'appuient fidèlement sur les relevés certifiés.")
        timeline.append({
            "ordre": ordre,
            "etape": "AUDIT_GREFFIER_PROCUREUR",
            "acteur": "Le Greffier d'audience",
            "role": "greffier",
            "avatar": "⚖️",
            "titre": "Contrôle factuel du Procureur",
            "texte": texte_greffier_p,
            "statut": "alerte" if non_v_p else "valide",
            "non_verifies": non_v_p,
            "pause_ms": 2000,
        })
        ordre += 1

    # 8. Verdict motivé du Président du Tribunal (Le Juge)
    juge = proces.motivation
    if juge:
        timeline.append({
            "ordre": ordre,
            "etape": "VERDICT_JUGE",
            "acteur": juge.role,
            "role": "juge",
            "avatar": "👨‍⚖️",
            "titre": f"Délibéré et Verdict officiel : {proces.decision['verdict']}",
            "verdict": proces.decision["verdict"],
            "texte": juge.texte,
            "pause_ms": 4500,
        })

    return timeline


def lancer_debat(persona, demande_utilisateur, mode: str = "gabarit") -> Proces:
    """Point d'entrée de haut niveau du débat du procès.
    
    Conforme à l'Issue 3.1 de la Roadmap :
    - `persona` : profil (instance de Profil ou clé 'amira', 'mateo', 'robert')
    - `demande_utilisateur` : texte d'intention libre ou tuple (ticker, taille)
    """
    from .profils import PROFILS, Profil
    from .intention import interpreter_intention

    if isinstance(persona, str):
        profil = PROFILS[persona.lower()]
    elif isinstance(persona, Profil):
        profil = persona
    else:
        raise TypeError("persona doit être un objet Profil ou une chaîne de caractères.")

    d = dn.charger()
    if isinstance(demande_utilisateur, str):
        ticker, taille, _ = interpreter_intention(demande_utilisateur, d.univers, profil)
    elif isinstance(demande_utilisateur, (tuple, list)):
        ticker, taille = demande_utilisateur[0], float(demande_utilisateur[1])
    else:
        ticker, taille = profil.demande_exemple

    return ouvrir_proces(profil, ticker, taille, mode=mode)
