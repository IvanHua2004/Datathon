"""Analyse comparative : Décision finale de l'investisseur (Oui/Non) versus Profil de base.

Permet à l'utilisateur d'arbitrer après avoir entendu le tribunal,
et quantifie immédiatement les répercussions de son choix sur son patrimoine.
"""
from __future__ import annotations

from dataclasses import dataclass
from . import moteur
from .format import dollars, pct, annees


@dataclass
class AnalyseComparative:
    choix: bool                      # True = OUI (investit), False = NON (renonce)
    titre_decision: str
    statut_conformite: str
    impact_capital: str
    profit_initial: float
    profit_final: float
    periode_debut: str
    periode_fin: str
    delta_perte_dollars: float
    perte_max_dollars: float
    budget_depasse: bool
    montant_depassement: float
    volatilite_finale: float
    delta_volatilite: float
    temps_recuperation: str
    commentaire_conseil: str
    recommandations: list[str]


def comparer_decision(dossier, decision_tribunal: dict, choix_investisseur: bool) -> AnalyseComparative:
    """Compare le résultat du choix (Oui/Non) par rapport au profil et portefeuille de départ."""
    p = dossier.profil
    t = dossier.ticker
    taille = dossier.taille
    av = dossier.avant
    ap = dossier.apres
    profit_initial = dossier.profit_initial
    profit_final = profit_initial
    if choix_investisseur:
        poids_finaux = moteur.ajouter_position(p.portefeuille, t, taille)
        profit_final = moteur.profit_portefeuille(
            dossier.donnees.rendements, poids_finaux, p.capital,
            dossier.debut, dossier.fin,
        )

    perte_av = av["pire_baisse"]["profondeur"] * p.capital
    perte_ap = ap["pire_baisse"]["profondeur"] * p.capital
    budget_dollars = -p.budget_perte * p.capital

    vol_av = av["volatilite_annuelle"]
    vol_ap = ap["volatilite_annuelle"]

    verdict = decision_tribunal["verdict"]

    if choix_investisseur:
        # L'utilisateur choisit d'investir malgré ou selon l'avis du tribunal
        delta_perte = perte_ap - perte_av
        depasse = (-perte_ap) > (-budget_dollars)
        montant_depasse = max(0.0, (-perte_ap) - (-budget_dollars))

        titre = f"DÉCISION : MAINTIEN DE L'ACHAT DE {pct(taille, 0)} DANS {t}"
        statut = ("Divergence avec le conseil prudentiel" if verdict in [
            "Contraire à une contrainte déclarée", "En tension avec le profil déclaré"
        ] else "Décision en accord avec le profil")

        impact = (f"En allouant {dollars(p.capital * taille)} sur {t}, la perte historique maximale "
                  f"{'de votre portefeuille' if p.portefeuille_declare else 'du portefeuille de référence'} "
                  f"passe de {dollars(perte_av)} à {dollars(perte_ap)} ({pct(ap['pire_baisse']['profondeur'])} du capital).")

        recommandations = []
        if depasse:
            recommandations.append(
                f"Budget de perte dépassé de {dollars(montant_depasse)} : prévoyez un fonds d'urgence séparé pour ne pas être contraint de liquider à perte."
            )
        if ap["contributions_risque"].get(t, 0) > 0.40:
            recommandations.append(
                f"Concentration critique : {t} porte {pct(ap['contributions_risque'][t])} du risque total. Surveillez activement cette ligne."
            )
        if not ap["pire_baisse"]["recupere"] or ap["pire_baisse"]["annees_sous_le_sommet"] > p.horizon_ans:
            recommandations.append(
                f"Horizon sous tension : le temps de recouvrement historique ({annees(ap['pire_baisse']['annees_sous_le_sommet'])}) approche ou dépasse votre horizon ({annees(p.horizon_ans)})."
            )
        if not recommandations:
            recommandations.append("Position compatible : maintenir un rééquilibrage trimestriel régulier.")

        comm = (f"Vous avez choisi de passer outre les réserves du tribunal. Le capital est plus exposé "
                f"(volatilité de {pct(vol_ap)} contre {pct(vol_av)} initialement).")

        return AnalyseComparative(
            choix=True,
            titre_decision=titre,
            statut_conformite=statut,
            impact_capital=impact,
            profit_initial=profit_initial,
            profit_final=profit_final,
            periode_debut=dossier.debut,
            periode_fin=dossier.fin,
            delta_perte_dollars=delta_perte,
            perte_max_dollars=perte_ap,
            budget_depasse=depasse,
            montant_depassement=montant_depasse,
            volatilite_finale=vol_ap,
            delta_volatilite=vol_ap - vol_av,
            temps_recuperation=annees(ap["pire_baisse"]["annees_sous_le_sommet"]),
            commentaire_conseil=comm,
            recommandations=recommandations,
        )
    else:
        # L'utilisateur choisit de renoncer à l'investissement
        titre = f"DÉCISION : ABANDON DU PROJET D'ACHAT DANS {t}"
        statut = "Protection du capital et respect strict des règles de prudence"
        impact = (f"Vous maintenez {p.mot_portefeuille} de base de {dollars(p.capital)}. "
                  f"Votre perte maximale observable reste bornée à {dollars(perte_av)} "
                  f"({pct(av['pire_baisse']['profondeur'])}), préservant une marge de sécurité de {dollars((-budget_dollars) - (-perte_av))} sous votre budget.")

        comm = (f"Excellente discipline d'investisseur. Vous évitez une potentielle aggravation de perte de "
                f"{dollars(abs(perte_ap - perte_av))} et maintenez une volatilité maîtrisée à {pct(vol_av)}.")

        recommandations = [
            f"Capital préservé : {dollars(p.capital * taille)} restent disponibles pour des opportunités plus conformes.",
            f"Stabilité assurée : votre horizon de {annees(p.horizon_ans)} n'est pas compromis par un titre volatil.",
            "Consultez les scénarios alternatifs ci-dessous pour trouver un véhicule d'investissement adapté."
        ]

        return AnalyseComparative(
            choix=False,
            titre_decision=titre,
            statut_conformite=statut,
            impact_capital=impact,
            profit_initial=profit_initial,
            profit_final=profit_final,
            periode_debut=dossier.debut,
            periode_fin=dossier.fin,
            delta_perte_dollars=0.0,
            perte_max_dollars=perte_av,
            budget_depasse=False,
            montant_depassement=0.0,
            volatilite_finale=vol_av,
            delta_volatilite=0.0,
            temps_recuperation=annees(av["pire_baisse"]["annees_sous_le_sommet"]),
            commentaire_conseil=comm,
            recommandations=recommandations,
        )
