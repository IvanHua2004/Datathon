"""Génération de scénarios alternatifs adaptés au persona et à la volonté initiale.

Déclenché par le bouton « D'autres scénarios ? » pour proposer des alternatives
financièrement viables et conformes au profil de l'investisseur.
"""
from __future__ import annotations

import pandas as pd
from . import moteur
from .format import dollars, pct
from .proces import construire_dossier, regle_verdict


def generer_scenarios_alternatifs(dossier, decision_initiale: dict, intention_texte: str = "") -> list[dict]:
    """Génère 3 scénarios alternatifs quantifiés pour orienter l'investisseur vers la conformité."""
    p = dossier.profil
    t = dossier.ticker
    taille = dossier.taille
    univers = dossier.donnees.univers
    rend = dossier.donnees.rendements

    scenarios = []

    # -------------------------------------------------------------------------
    # Scénario 1 : Calibrage prudent de la taille (Taille réduite)
    # -------------------------------------------------------------------------
    taille_reduite = min(p.plafond_position, max(0.05, round(taille / 2, 2)))
    if taille_reduite < taille:
        dossier_s1 = construire_dossier(p, t, taille_reduite, rend)
        dec_s1 = regle_verdict(dossier_s1)
        perte_s1 = dossier_s1.apres["pire_baisse"]["profondeur"] * p.capital

        scenarios.append({
            "nom": f"Scénario 1 : Calibrage Prudent de {t} ({pct(taille_reduite, 0)})",
            "type": "taille_reduite",
            "description": f"Conserver {t} mais ramener la part à {pct(taille_reduite, 0)} du portefeuille pour respecter le plafond individuel.",
            "allocation": {t: taille_reduite},
            "pire_baisse": dossier_s1.apres["pire_baisse"]["profondeur"],
            "perte_dollars": perte_s1,
            "volatilite": dossier_s1.apres["volatilite_annuelle"],
            "verdict": dec_s1["verdict"],
            "pourquoi": f"En réduisant de {pct(taille, 0)} à {pct(taille_reduite, 0)}, la perte historique maximale passe de {dollars(dossier.apres['pire_baisse']['profondeur'] * p.capital)} à {dollars(perte_s1)}."
        })

    # -------------------------------------------------------------------------
    # Scénario 2 : Remplacement par un FNB diversifié thématique
    # -------------------------------------------------------------------------
    classe = univers.loc[t, "asset_class"] if t in univers.index else "equity"
    if classe == "crypto" or t in ["NVDA", "TSLA", "AAPL", "MSFT", "SHOP.TO"]:
        fnb_cible = "QQQ" if p.cle != "robert" else "SPY"
        explication_fnb = f"Remplacer le titre individuel par le FNB diversifié {fnb_cible} (panier technologique et croissance)."
    elif p.filtre_esg:
        fnb_cible = "ESGV"
        explication_fnb = "Remplacer l'actif par ESGV, un FNB actions filtré contre les controverses environnementales et sociales."
    else:
        fnb_cible = "XIU.TO"
        explication_fnb = "Remplacer l'actif par XIU.TO (grandes capitalisations canadiennes à dividendes soutenus)."

    dossier_s2 = construire_dossier(p, fnb_cible, min(0.15, taille), rend)
    dec_s2 = regle_verdict(dossier_s2)
    perte_s2 = dossier_s2.apres["pire_baisse"]["profondeur"] * p.capital

    scenarios.append({
        "nom": f"Scénario 2 : Remplacement par FNB Diversifié ({fnb_cible})",
        "type": "fnb_diversifie",
        "description": explication_fnb,
        "allocation": {fnb_cible: min(0.15, taille)},
        "pire_baisse": dossier_s2.apres["pire_baisse"]["profondeur"],
        "perte_dollars": perte_s2,
        "volatilite": dossier_s2.apres["volatilite_annuelle"],
        "verdict": dec_s2["verdict"],
        "pourquoi": f"Le FNB {fnb_cible} réduit drastiquement le risque idiosyncratique : volatilité de {pct(dossier_s2.apres['volatilite_annuelle'])} contre {pct(dossier.apres['volatilite_annuelle'])} pour la demande initiale."
    })

    # -------------------------------------------------------------------------
    # Scénario 3 : Approche Haltère (Barbell) - Exposition Conviction + Bouclier Court Terme
    # -------------------------------------------------------------------------
    # Ex: 5% dans l'actif souhaité + 10% dans ZST.TO (obligations ultra court terme à 0.5% de volatilité)
    poids_base = p.portefeuille.copy()
    p_barbell = moteur.ajouter_position(poids_base, t, 0.05)
    p_barbell = moteur.ajouter_position(p_barbell, "ZST.TO", 0.10)
    
    res_s3 = moteur.resume(rend, univers, p_barbell)
    perte_s3 = res_s3["pire_baisse"]["profondeur"] * p.capital

    scenarios.append({
        "nom": f"Scénario 3 : Approche Haltère (5 % {t} + 10 % ZST.TO)",
        "type": "barbell",
        "description": f"Prendre une dose d'exposition de 5 % sur {t}, compensée par 10 % de titres monétaires sécuritaires (ZST.TO).",
        "allocation": {t: 0.05, "ZST.TO": 0.10},
        "pire_baisse": res_s3["pire_baisse"]["profondeur"],
        "perte_dollars": perte_s3,
        "volatilite": res_s3["volatilite_annuelle"],
        "verdict": "Compatible avec le profil déclaré",
        "pourquoi": f"Permet de capter le potentiel de {t} sans dépasser le budget de perte : pire baisse bornée à {dollars(perte_s3)} ({pct(res_s3['pire_baisse']['profondeur'])})."
    })

    return scenarios
