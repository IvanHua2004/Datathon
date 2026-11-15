"""Les témoins : chacun est le seul à lire sa source et ne dépose que des faits.

Un témoin ne donne pas d'opinion. S'il n'a rien, il le dit.
"""
from __future__ import annotations

import pandas as pd

from . import donnees as dn
from .format import annees, dollars, nombre, pct
from .greffier import Greffier, Piece

LIMITES_PRIX = ("Cinq ans de données, une seule grande crise observée (2022). Univers choisi en "
                "2026 parmi des titres aujourd'hui importants : biais du survivant. Portefeuille "
                "à poids constants. Le passé ne prédit pas l'avenir.")

DESCRIPTIONS = {
    "risque": "pertes observées en pourcentage et en dollars, temps de récupération, part du risque",
    "diversification": "comportement du titre les pires jours du portefeuille, concentration par "
                       "secteur et par devise",
    "valeurs": "preuves ESG collectées à la main par l'équipe dans des documents publics",
    "macro": "taux directeur, rendement obligataire et inflation pendant la pire baisse",
    "action": "fiche d'identité financière avancée précalculée : VaR, Sharpe, Bêta, dividende, moments",
    "simulation": "simulations probabilistes et historiques : pire cas de perte, cas probable moyen, meilleur cas de gain",
}


def _recuperation(pb: dict) -> str:
    texte = annees(pb["annees_sous_le_sommet"])
    return texte if pb["recupere"] else texte + " au moins (sommet non retrouvé à la fin des données)"


def risque(dossier, greffier: Greffier, appele_par: str) -> Piece:
    av, ap, p, t = dossier.avant, dossier.apres, dossier.profil, dossier.ticker
    faits = {
        "Pire baisse observée, portefeuille actuel": pct(av["pire_baisse"]["profondeur"]),
        "Pire baisse observée, avec la position": pct(ap["pire_baisse"]["profondeur"]),
        "Perte en dollars au pire creux, portefeuille actuel": dollars(av["pire_baisse"]["profondeur"] * p.capital),
        "Perte en dollars au pire creux, avec la position": dollars(ap["pire_baisse"]["profondeur"] * p.capital),
        "Budget de perte déclaré (hypothèse du profil)": f"{pct(-p.budget_perte)}, soit {dollars(-p.budget_perte * p.capital)}",
        "Pire baisse avec la position, du sommet au creux": f"{ap['pire_baisse']['date_sommet']} au {ap['pire_baisse']['date_creux']}",
        "Temps passé sous le sommet, portefeuille actuel": _recuperation(av["pire_baisse"]),
        "Temps passé sous le sommet, avec la position": _recuperation(ap["pire_baisse"]),
        "Rendement de l'année 2022, portefeuille actuel": pct(av["rendement_2022"]),
        "Rendement de l'année 2022, avec la position": pct(ap["rendement_2022"]),
        "Pire baisse sur 12 mois, cas défavorable (5 % des tirages), actuel": pct(av["fourchette_12_mois"]["defavorable_5pct"]),
        "Pire baisse sur 12 mois, cas défavorable (5 % des tirages), avec la position": pct(ap["fourchette_12_mois"]["defavorable_5pct"]),
        f"Poids de {t} avec la position": pct(ap["poids"].get(t, 0.0)),
        f"Part du risque total portée par {t}": pct(ap["contributions_risque"].get(t, 0.0)),
        f"Pire baisse observée de {t} seul": pct(dossier.titre_seul["profondeur"]),
        "Volatilité annuelle, portefeuille actuel": pct(av["volatilite_annuelle"]),
        "Volatilité annuelle, avec la position": pct(ap["volatilite_annuelle"]),
    }
    return greffier.deposer(
        temoin="risque", outil="rdc.moteur.resume", appele_par=appele_par,
        parametres={"ticker": t, "taille": dossier.taille, "capital": p.capital},
        faits=faits, source=dossier.donnees.source(),
        periode=f"{dossier.debut} au {dossier.fin}",
        limites=LIMITES_PRIX + " La fourchette sur 12 mois vient d'un rééchantillonnage par blocs "
                               "d'un mois : elle ne peut pas inventer des crises jamais observées.",
    )


def diversification(dossier, greffier: Greffier, appele_par: str) -> Piece:
    c, t = dossier.crise, dossier.ticker
    cav, cap = dossier.avant["concentration"], dossier.apres["concentration"]
    secteur = dossier.secteur
    faits = {
        f"Corrélation de {t} avec le portefeuille, jours calmes": nombre(c["correlation_jours_calmes"]),
        f"Corrélation de {t} avec le portefeuille, jours de crise": nombre(c["correlation_jours_de_crise"]),
        "Nombre de jours de crise (10 % des pires jours du portefeuille actuel)": str(c["nb_jours_de_crise"]),
        f"Rendement moyen de {t} ces jours-là": pct(c["rendement_moyen_titre_jours_de_crise"], 2),
        "Rendement moyen du portefeuille actuel ces jours-là": pct(c["rendement_moyen_portefeuille_jours_de_crise"], 2),
        f"Secteur de {t} (étiquette des organisateurs)": secteur,
        f"Poids du secteur {secteur}, avant": pct(cav["par_secteur"].get(secteur, 0.0)),
        f"Poids du secteur {secteur}, avec la position": pct(cap["par_secteur"].get(secteur, 0.0)),
        "Exposition au dollar américain, avant": pct(cav["par_devise"].get("USD", 0.0)),
        "Exposition au dollar américain, avec la position": pct(cap["par_devise"].get("USD", 0.0)),
        "Plus grosse position avec la demande": f"{cap['plus_grosse_position']['ticker']} à {pct(cap['plus_grosse_position']['poids'])}",
    }
    return greffier.deposer(
        temoin="diversification", outil="rdc.moteur.comportement_en_crise + concentration",
        appele_par=appele_par, parametres={"ticker": t, "taille": dossier.taille},
        faits=faits, source=dossier.donnees.source() + " ; assets_universe.csv",
        periode=f"{dossier.debut} au {dossier.fin}",
        limites=LIMITES_PRIX + " Les FNB ne sont pas décomposés en titres : la concentration "
                               "cachée (par exemple un titre déjà présent dans un FNB) n'est pas mesurée.",
    )


def lire_preuves_esg(ticker: str) -> pd.DataFrame:
    chemin = dn.RACINE / "donnees_externes" / "esg_preuves.csv"
    if not chemin.exists():
        return pd.DataFrame()
    table = pd.read_csv(chemin, dtype=str).fillna("")
    return table[table["ticker"] == ticker]


def valeurs(dossier, greffier: Greffier, appele_par: str) -> Piece:
    t = dossier.ticker
    preuves = dossier.preuves_esg
    faits = {f"Secteur de {t} (étiquette des organisateurs)": dossier.secteur}
    if preuves.empty:
        faits[f"Preuves ESG collectées pour {t}"] = "aucune preuve dans nos sources"
    else:
        faits[f"Preuves ESG collectées pour {t}"] = str(len(preuves))
        for i, ligne in enumerate(preuves.itertuples(), start=1):
            faits[f"Preuve {i} ({ligne.type}, {ligne.nature})"] = (
                f"{ligne.fait} | {ligne.source}, {ligne.date_document} | {ligne.url}")
    return greffier.deposer(
        temoin="valeurs", outil="lecture de donnees_externes/esg_preuves.csv",
        appele_par=appele_par, parametres={"ticker": t}, faits=faits,
        source="Table de preuves ESG collectées à la main par l'équipe (documents publics)",
        periode="voir la date de chaque document",
        limites="Le jeu de départ ne contient aucune donnée ESG. L'absence de preuve dans la "
                "table ne prouve pas l'absence de controverse.",
    )


def macro(dossier, greffier: Greffier, appele_par: str) -> Piece:
    pb = dossier.apres["pire_baisse"]
    faits: dict[str, str] = {}
    series = [("V39079", "Taux directeur de la Banque du Canada"),
              ("BD.CDN.10YR.DQ.YLD", "Rendement des obligations du Canada à 10 ans"),
              ("DFF", "Taux des fonds fédéraux américains")]
    for code, libelle in series:
        for moment, date in (("au sommet", pb["date_sommet"]), ("au creux", pb["date_creux"])):
            v = dn.valeur_macro(code, date)
            if v:
                faits[f"{libelle}, {moment} ({v[1]})"] = nombre(v[0]) + " %"
    ipc = dn.valeur_macro("STATIC_TOTALCPICHANGE", pb["date_creux"], delai_publication_jours=45)
    if ipc:
        faits[f"Inflation au Canada sur un an, dernière valeur publiée au creux (mois de référence {ipc[1][:7]})"] = nombre(ipc[0], 1) + " %"
    fx_debut = dn.valeur_fx(pb["date_sommet"])
    fx_fin = dn.valeur_fx(pb["date_creux"])
    if fx_debut and fx_fin:
        faits["Dollar américain en dollars canadiens, du sommet au creux"] = f"{nombre(fx_debut, 4)} à {nombre(fx_fin, 4)}"
    return greffier.deposer(
        temoin="macro", outil="rdc.donnees.valeur_macro", appele_par=appele_par,
        parametres={"date_sommet": pb["date_sommet"], "date_creux": pb["date_creux"]},
        faits=faits,
        source="macro_rates.csv (Banque du Canada, FRED) ; fx_usdcad_daily.csv (Banque du Canada)",
        periode=f"{pb['date_sommet']} au {pb['date_creux']}",
        limites="L'inflation mensuelle est prise avec 45 jours de délai de publication (hypothèse) "
                "pour ne pas utiliser une valeur avant qu'elle soit connue. Les séries FRED sont "
                "les valeurs révisées, pas celles publiées à l'époque. Contexte, pas une cause prouvée.",
    )


def action_temoin(dossier, greffier: Greffier, appele_par: str) -> Piece:
    """Témoin de la fiche financière de l'action : dépose les métriques quantitatives précalculées."""
    from . import actions_store
    t = dossier.ticker
    fiche = actions_store.obtenir_fiche_action(t)
    r = fiche["rendements"]
    rq = fiche["risque"]
    rp = fiche["ratios_performance"]
    sm = fiche["sensibilites_marche_et_macro"]
    ac = fiche["actions_corporatives"]
    faits = {
        f"Nom et secteur de {t}": f"{fiche['nom']} ({fiche['secteur']})",
        f"Rendement annualisé 5 ans (CAGR) de {t}": pct(r["cagr_annualise"]),
        f"Rendement 1 an de {t}": pct(r["rendement_1an"]),
        f"Volatilité annuelle de {t}": pct(rq["volatilite_annuelle"]),
        f"Pire baisse observée (Max Drawdown) de {t}": pct(rq["pire_baisse_globale"]),
        f"Value at Risk quotidienne 95 % (VaR) de {t}": pct(rq["var_95_quotidienne"]),
        f"Conditional VaR quotidienne 95 % (Expected Shortfall) de {t}": pct(rq["cvar_95_expected_shortfall"]),
        f"Ratio de Sharpe de {t}": nombre(rp["ratio_sharpe"]),
        f"Ratio de Sortino de {t}": nombre(rp["ratio_sortino"]),
        f"Bêta par rapport au S&P 500 (SPY CAD) de {t}": nombre(sm.get("beta_spy_cad", 1.0)),
        f"Rendement du dividende estimé de {t}": pct(ac["rendement_dividende_pct"]),
        f"Fréquence des dividendes de {t}": str(ac["frequence_dividende"]),
        f"Diagnostic de distribution de {t}": str(fiche["distribution"]["diagnostic"]),
    }
    return greffier.deposer(
        temoin="action", outil="rdc.actions_store.obtenir_fiche_action",
        appele_par=appele_par, parametres={"ticker": t},
        faits=faits, source="Fiche précalculée persistée S3 / Local (prices_daily.csv, corporate_actions.csv)",
        periode=f"{r['date_debut']} au {r['date_fin']}",
        limites="Métriques historiques basées sur le passé observé (2021-2026). Ne garantissent pas le futur.",
    )


def simulation(dossier, greffier: Greffier, appele_par: str) -> Piece:
    """Témoin des simulations financières : modélise le pire cas, cas moyen et meilleur cas."""
    from . import simulateur
    simu = simulateur.simuler_impact_decision(dossier)
    pire = simu.pire_cas
    moyen = simu.cas_probable
    meilleur = simu.meilleur_cas

    faits = {
        "Capital engagé de départ": dollars(simu.capital_initial),
        "Pire cas de perte (Stress-test historique)": f"{dollars(pire.impact_dollars)} ({pct(pire.rendement_pct)})",
        "Pire creux projeté du portefeuille": dollars(pire.capital_final),
        "Période du pire creux historique": f"{pire.date_debut} au {pire.date_fin}",
        "Cas probable / moyen (Rendement 1 an)": f"+{dollars(moyen.impact_dollars)} (+{pct(moyen.rendement_pct)} / an)",
        "Capital final projeté au cas moyen": dollars(moyen.capital_final),
        "Meilleur cas de gain (Rallye haussier 1 an)": f"+{dollars(meilleur.impact_dollars)} (+{pct(meilleur.rendement_pct)})",
        "Capital final projeté au meilleur cas": dollars(meilleur.capital_final),
        "Période du meilleur rallye historique": f"{meilleur.date_debut} au {meilleur.date_fin}",
        "Budget de perte maximal déclaré": f"{pct(simu.budget_perte_pct)} ({dollars(simu.budget_perte_dollars)})",
        "Statut de conformité du pire cas": pire.statut_libelle,
        "Impact net du pire cas vs portefeuille actuel": dollars(pire.delta_vs_actuel_dollars),
        "Gain annuel additionnel vs portefeuille actuel": dollars(moyen.delta_vs_actuel_dollars),
        "Potentiel haussier additionnel vs portefeuille actuel": dollars(meilleur.delta_vs_actuel_dollars),
    }
    return greffier.deposer(
        temoin="simulation", outil="rdc.simulateur.simuler_impact_decision", appele_par=appele_par,
        parametres={"ticker": dossier.ticker, "taille": dossier.taille, "capital": simu.capital_initial},
        faits=faits, source="Séries temporelles historiques en CAD (1 304 séances quotidiennes, 2021-2026)",
        periode=f"{dossier.debut} au {dossier.fin}",
        limites="Projections fondées sur les séances historiques observées à poids constants. "
                "Le passé ne constitue pas une garantie du futur.",
    )


TEMOINS = {
    "risque": risque,
    "diversification": diversification,
    "valeurs": valeurs,
    "macro": macro,
    "action": action_temoin,
    "simulation": simulation,
}
