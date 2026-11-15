"""Les agents : Défense, Procureur, Juge.

Deux modes :
- « gabarit » : textes construits par des règles, sans modèle de langage. Sert à développer,
  à tester et de filet de sécurité pendant la démo.
- « bedrock » : agents Strands sur Amazon Bedrock. La Défense et le Procureur décident
  eux-mêmes quels témoins convoquer avec l'outil `convoquer_temoin`.

Dans les deux modes, les chiffres viennent des pièces et le verdict vient de la règle.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from . import temoins
from .format import annees, dollars, pct

CONSIGNE_COMMUNE = """Tu participes à un procès simulé appelé « Règlement de comptes ». Un investisseur
FICTIF soumet une demande d'investissement ; le tribunal examine si elle est cohérente avec le
profil qu'il a déclaré. C'est une simulation pédagogique, jamais un conseil financier.

Règles strictes :
- Avant de parler, convoque les témoins utiles avec l'outil convoquer_temoin. Ne convoque que
  ceux qui servent ton argument.
- Tu ne cites QUE des chiffres présents dans les pièces, recopiés exactement, suivis du numéro
  de la pièce entre crochets, par exemple [P-01]. Aucun autre chiffre.
- Tu ne prédis aucun rendement futur et tu ne dis jamais à l'investisseur quoi acheter ou vendre.
- Si un témoin n'a pas de preuve, dis-le au lieu de supposer.
- Réponds en français, en 120 mots au maximum, sans titre ni liste."""

ROLE_DEFENSE = """Ton rôle : LA DÉFENSE. Tu présentes le meilleur argument honnête EN FAVEUR de la
demande, à partir de l'objectif et des préférences de l'investisseur et des pièces. Tu reconnais
en une phrase la limite la plus sérieuse de ta position."""

ROLE_PROCUREUR = """Ton rôle : LE PROCUREUR. Au nom du profil déclaré, tu attaques la demande : pertes en
dollars, horizon, concentration, contraintes et valeurs. Tu réponds à l'argument de la Défense.
Tu ne t'opposes pas par principe : si les pièces ne soutiennent pas une objection, tu ne la fais pas."""

ROLE_JUGE = """Ton rôle : LE JUGE. Le verdict est déjà fixé par la règle du tribunal ; tu ne peux pas le
changer. Tu rédiges les motifs en 150 mots au maximum, en répondant dans l'ordre à : quelles
données ont été utilisées, pourquoi ce verdict, quelles limites, et qu'est-ce qui changerait la
réponse (utilise le résultat de la salle). Cite les pièces entre crochets. Ne recommande rien :
c'est l'investisseur qui décide."""

ROLE_SIMULATEUR = """Ton rôle : L'EXPERT SIMULATEUR FINANCIER (Dr. Sterling). Tu déposes sous serment
devant le tribunal pour éclairer la décision financière sur la base des simulations patrimoniales
fondées sur les données historiques observables (1 304 séances en CAD, 2021-2026).
Tu présentes avec rigueur, concision et neutralité les 3 scénarios d'arbitrage patrimonial :
1. LE PIRE CAS DE PERTE : baisse maximale pic-au-creux observée (en $ et en %), dates exactes de la crise
   et statut par rapport au budget de perte déclaré par l'investisseur.
2. LE CAS PROBABLE / MOYEN : espérance centrale basée sur le rendement annualisé composé (CAGR) et la médiane
   glissante sur 1 an, impact en dollars et capital projeté.
3. LE MEILLEUR CAS DE GAIN : potentiel haussier maximal observé sur 12 mois consécutifs (en $ et en %).
4. L'IMPACT NET : ce que cette décision apporte de plus ou de moins par rapport au portefeuille actuel (statu quo).
Règles strictes :
- Cite les chiffres exacts des pièces scellées entre crochets, par exemple [P-01] ou [P-02].
- Ne prédis pas l'avenir et ne donne aucun conseil personnel d'achat ou de vente.
- Réponds en français en 120 mots au maximum, de manière percutante, claire et pédagogique."""

ROLES_TEMOINS = {
    "risque": """Ton rôle : Dr. Laurent (Expert Actuaire du Risque). Tu déposes sous serment à la barre.
Tu analyses l'impact de la décision financière sur la pire baisse historique du portefeuille et la perte maximale en dollars au creux, en la comparant directement au budget de perte déclaré par l'investisseur.
Tu expliques avec rigueur et neutralité si cette décision fait exploser ou respecte la tolérance au risque de l'investisseur.
Règles strictes :
- Cite les chiffres exacts de ta pièce scellée entre crochets (ex: [P-01]). Aucun autre chiffre.
- Reste factuel, sans donner de conseil financier.
- Réponds en français en 100 mots maximum.""",

    "diversification": """Ton rôle : Mme Chantal (Cartographe de Portefeuille). Tu déposes sous serment à la barre.
Tu analyses la diversification sectorielle et le comportement du titre lors des 10 % pires séances de tempête boursière.
Tu réfléchis et expliques si le titre amortit les chocs ou s'il amplifie les pertes en période de crise de marché.
Règles strictes :
- Cite les chiffres exacts de ta pièce scellée entre crochets. Aucun autre chiffre.
- Reste factuelle et pédagogique.
- Réponds en français en 100 mots maximum.""",

    "valeurs": """Ton rôle : Me Tremblay (Auditeur ESG & Gouvernance). Tu déposes sous serment à la barre.
Tu analyses la conformité de l'investissement avec les critères d'exclusion et valeurs éthiques déclarées par l'investisseur.
Tu déposes tes conclusions d'audit avec neutralité sur la base des preuves documentaires publiques scellées.
Règles strictes :
- Cite les faits constatés dans ta pièce entre crochets.
- Reste objectif et factuel.
- Réponds en français en 100 mots maximum.""",

    "macro": """Ton rôle : M. Raymond (Observateur Macroéconomique). Tu déposes sous serment à la barre.
Tu analyses le contexte macroéconomique (taux d'intérêt de la Banque du Canada, inflation IPC, rendements obligataires) observé lors des pires chocs historiques et son impact sur la sensibilité du portefeuille.
Règles strictes :
- Cite les chiffres exacts de ta pièce entre crochets.
- Reste rigoureux et neutre.
- Réponds en français en 100 mots maximum.""",

    "action": """Ton rôle : Dr. Laurent (Analyste Quantitatif & Risque de Queue). Tu déposes sous serment à la barre.
Tu analyses la fiche technique avancée de l'actif : Value at Risk (VaR 95%), Expected Shortfall (CVaR), Bêta et ratio de Sharpe.
Tu réfléchis à la prime de risque et au risque extrême apporté par cette position.
Règles strictes :
- Cite les chiffres exacts de ta pièce scellée entre crochets.
- Reste rigoureux et analytique.
- Réponds en français en 100 mots maximum.""",

    "simulation": ROLE_SIMULATEUR,
}


@dataclass
class Plaidoirie:
    role: str
    texte: str
    temoins_convoques: list[str] = field(default_factory=list)
    non_verifies: list[str] = field(default_factory=list)


def _convocateur(proces, role: str, convoques: list[str]):
    def convoquer(nom: str) -> str:
        nom = nom.strip().lower()
        if nom not in temoins.TEMOINS:
            return f"Témoin inconnu. Témoins disponibles : {', '.join(temoins.TEMOINS)}."
        piece = temoins.TEMOINS[nom](proces.dossier, proces.greffier, role)
        if nom not in convoques:
            convoques.append(nom)
        return piece.en_texte()
    return convoquer


def _expose(proces) -> str:
    d, p = proces.dossier, proces.dossier.profil
    volonte = f"Volonté libre formulée par l'investisseur : « {proces.intention_texte} ». " if getattr(proces, "intention_texte", "") else ""
    return (f"Investisseur fictif : {p.nom}. {p.resume} Objectif : {p.objectif} "
            f"Préférences : {p.preferences} Capital : {dollars(p.capital)}. "
            f"{volonte}"
            f"Demande soumise au tribunal : placer {pct(d.taille, 0)} du portefeuille dans {d.ticker} "
            f"({d.donnees.univers.loc[d.ticker, 'name']}), financé au prorata des autres positions."
            + ("" if p.portefeuille_declare else
               " Les positions réelles de l'investisseur ne sont pas connues : le portefeuille étudié est un "
               "portefeuille de référence fictif. Ne dites jamais « votre portefeuille » ni « vos positions » ; "
               "dites « le portefeuille de référence »."))


def _faits(proces, temoin: str) -> tuple[str, dict]:
    for piece in proces.greffier.pieces:
        if piece.temoin == temoin:
            return piece.numero, piece.faits
    raise KeyError(temoin)


# ----------------------------------------------------------------------------- mode gabarit & bedrock pour témoins
def depositions_temoins_incarnee(proces) -> list[dict]:
    """Chaque témoin dépose sous serment à la barre sous forme de personnage incarné.
    
    En mode 'bedrock', chaque témoin est un agent LLM spécialisé qui réfléchit à l'impact
    en se basant strictement sur sa pièce scellée locale (calculs déterministes 1 304 séances).
    En mode 'gabarit' (ou si Bedrock échoue), le témoin utilise un gabarit déterministe certifié.
    """
    resultats = []
    d, p, t = proces.dossier, proces.dossier.profil, proces.dossier.ticker
    mode = getattr(proces, "mode", "gabarit")

    for piece in proces.greffier.pieces:
        f = piece.faits
        n = piece.numero
        if piece.temoin == "risque":
            fallback = (f"Monsieur le Président, je dépose sous serment la pièce [{n}]. L'analyse de 1 304 séances "
                        f"démontre que la pire baisse du portefeuille passerait de {f['Pire baisse observée, portefeuille actuel']} "
                        f"à {f['Pire baisse observée, avec la position']} (soit {f['Perte en dollars au pire creux, avec la position']} "
                        f"pour un budget déclaré de {f['Budget de perte déclaré (hypothèse du profil)']}). "
                        f"Le titre {t} porterait à lui seul {f[f'Part du risque total portée par {t}']} du risque global.")
            texte = invoquer_temoin_bedrock(proces, piece, ROLES_TEMOINS.get("risque", ""), fallback) if mode == "bedrock" else fallback
            resultats.append({
                "temoin": "risque",
                "personnage": "Dr. Laurent (Expert Actuaire)",
                "role": "Témoin du Risque",
                "piece": n,
                "texte": texte,
                "non_verifies": proces.greffier.verifier(texte),
            })
        elif piece.temoin == "diversification":
            titre_crise = f.get(f"Rendement moyen de {t} ces jours-là", "N/A")
            pf_crise = f.get("Rendement moyen du portefeuille actuel ces jours-là", "N/A")
            fallback = (f"À la barre, je verse la pièce [{n}] au dossier. Lors des 10 % pires jours de tempête boursière, "
                        f"{t} affiche un rendement moyen de {titre_crise} contre {pf_crise} pour le reste du portefeuille. "
                        f"L'exposition au secteur {f.get(f'Secteur de {t} (étiquette des organisateurs)', 'Inconnu')} passerait à "
                        f"{f.get(f'Poids du secteur {d.secteur}, avec la position', 'N/A')}.")
            texte = invoquer_temoin_bedrock(proces, piece, ROLES_TEMOINS.get("diversification", ""), fallback) if mode == "bedrock" else fallback
            resultats.append({
                "temoin": "diversification",
                "personnage": "Mme Chantal (Cartographe de Portefeuille)",
                "role": "Témoin de la Diversification",
                "piece": n,
                "texte": texte,
                "non_verifies": proces.greffier.verifier(texte),
            })
        elif piece.temoin == "valeurs":
            fallback = (f"En tant qu'auditeur de conformité ESG, je dépose la pièce [{n}]. Nos investigations publiques "
                        f"attestent : {f.get(f'Preuves ESG collectées pour {t}', 'aucune preuve')}. Le respect des exigences morales de {p.nom} "
                        f"dépend strictement de ces éléments factuels.")
            texte = invoquer_temoin_bedrock(proces, piece, ROLES_TEMOINS.get("valeurs", ""), fallback) if mode == "bedrock" else fallback
            resultats.append({
                "temoin": "valeurs",
                "personnage": "Me Tremblay (Auditeur ESG & Gouvernance)",
                "role": "Témoin des Valeurs",
                "piece": n,
                "texte": texte,
                "non_verifies": proces.greffier.verifier(texte),
            })
        elif piece.temoin == "macro":
            fallback = (f"J'atteste sous serment des conditions macroéconomiques via la pièce [{n}]. Lors de la pire baisse "
                        f"du sommet au creux, la hausse brutale des taux d'intérêt et l'inflation ont brisé les corrélations habituelles.")
            texte = invoquer_temoin_bedrock(proces, piece, ROLES_TEMOINS.get("macro", ""), fallback) if mode == "bedrock" else fallback
            resultats.append({
                "temoin": "macro",
                "personnage": "M. Raymond (Observateur des Banques Centrales)",
                "role": "Témoin Macroéconomie",
                "piece": n,
                "texte": texte,
                "non_verifies": proces.greffier.verifier(texte),
            })
        elif piece.temoin == "action":
            fallback = (f"En qualité d'analyste quantitatif, je dépose sous serment la fiche technique [{n}] de l'action {t}. "
                        f"L'actif enregistre un ratio de Sharpe de {f.get(f'Ratio de Sharpe de {t}', 'N/A')}, un Bêta de {f.get(f'Bêta par rapport au S&P 500 (SPY CAD) de {t}', 'N/A')} "
                        f"et une VaR quotidienne à 95% de {f.get(f'Value at Risk quotidienne 95 % (VaR) de {t}', 'N/A')} "
                        f"(Expected Shortfall CVaR de {f.get(f'Conditional VaR quotidienne 95 % (Expected Shortfall) de {t}', 'N/A')}).")
            texte = invoquer_temoin_bedrock(proces, piece, ROLES_TEMOINS.get("action", ""), fallback) if mode == "bedrock" else fallback
            resultats.append({
                "temoin": "action",
                "personnage": "Dr. Laurent (Analyste Quantitatif & Risque de Queue)",
                "role": "Témoin Analyse Financière de l'Action",
                "piece": n,
                "texte": texte,
                "non_verifies": proces.greffier.verifier(texte),
            })
        elif piece.temoin == "simulation":
            from . import simulateur
            simu = getattr(proces, "simulation", None)
            if simu is None:
                simu = simulateur.simuler_impact_decision(d)
                proces.simulation = simu
            if mode == "bedrock":
                texte = invoquer_simulateur_bedrock(proces, simu)
            else:
                texte = simulateur.generer_deposition_simulateur(simu)
            resultats.append({
                "temoin": "simulation",
                "personnage": "Dr. Sterling (L'Actuaire Simulateur)",
                "role": "Expert quantitatif et stress-testing patrimonial",
                "piece": n,
                "texte": texte,
                "non_verifies": proces.greffier.verifier(texte),
            })
    return resultats


def _defense_gabarit(proces) -> Plaidoirie:
    d, p, t = proces.dossier, proces.dossier.profil, proces.dossier.ticker
    convoques: list[str] = []
    _convocateur(proces, "la Défense", convoques)("risque")
    n, f = _faits(proces, "risque")
    objectif = p.objectif[0].lower() + p.objectif[1:].rstrip(".")
    phrases = [
        f"Monsieur le Président, mesdames et messieurs du tribunal ! Mon client {p.nom} se présente avec une ambition légitime : {objectif}.",
        f"La demande reste mesurée à {f[f'Poids de {t} avec la position']} du portefeuille [{n}]."
    ]
    if d.apres["pire_baisse"]["recupere"] and d.apres["pire_baisse"]["annees_sous_le_sommet"] <= p.horizon_ans:
        phrases.append(f"Dans les faits observés, le portefeuille avec la position est revenu à son sommet en "
                       f"{f['Temps passé sous le sommet, avec la position']} [{n}], moins que l'horizon de "
                       f"{annees(p.horizon_ans)}.")
    avant, apres = f["Pire baisse observée, portefeuille actuel"], f["Pire baisse observée, avec la position"]
    if d.apres["pire_baisse"]["profondeur"] >= d.avant["pire_baisse"]["profondeur"]:
        phrases.append(f"La pire baisse observée ne s'aggrave pas : elle passe de {avant} à {apres} [{n}]. "
                       f"Nous reconnaissons la limite : cinq ans d'histoire ne garantissent pas l'avenir, mais le dynamisme de {p.nom} mérite d'être soutenu !")
    else:
        phrases.append(f"Je reconnais la limite : la pire baisse observée passe de {avant} à {apres} [{n}], "
                       f"mais refuser cette opportunité par excès de frilosité condamnerait {p.nom} à la stagnation financière !")
    return Plaidoirie("Me Vigor (La Défense)", " ".join(phrases), convoques)


def _procureur_gabarit(proces) -> Plaidoirie:
    d, p, t = proces.dossier, proces.dossier.profil, proces.dossier.ticker
    convoques: list[str] = []
    convoquer = _convocateur(proces, "le Procureur", convoques)
    convoquer("risque")
    convoquer("diversification")
    convoquer("simulation")
    if p.filtre_esg:
        convoquer("valeurs")
    if p.horizon_ans <= 5:
        convoquer("macro")
    nr, fr = _faits(proces, "risque")
    nd, fd = _faits(proces, "diversification")
    ns, fs = _faits(proces, "simulation")
    phrases = ["Objection véhémente, Votre Honneur ! Mon rôle de procureur est de protéger l'investisseur contre l'aveuglement."]
    budget = fr["Budget de perte déclaré (hypothèse du profil)"]
    avant = fr["Perte en dollars au pire creux, portefeuille actuel"]
    apres = fr["Perte en dollars au pire creux, avec la position"]
    if d.apres["pire_baisse"]["profondeur"] < d.avant["pire_baisse"]["profondeur"]:
        phrases.append(f"Les chiffres ne mentent pas : au pire creux, la perte bondirait de {avant} à {apres}, pour un budget de perte déclaré de seulement {budget} [{nr}] !")
    else:
        phrases.append(f"Au pire creux, la perte atteindrait {apres}, pour un budget déclaré de {budget} [{nr}].")
    pire_creux = fs["Pire creux projeté du portefeuille"]
    phrases.append(f"L'Expert Simulateur le confirme dans la pièce [{ns}] : dans le pire scénario historique, le capital résiduel tomberait à {pire_creux} !")
    part = d.apres["contributions_risque"].get(t, 0.0)
    if part > d.apres["poids"].get(t, 0.0):
        phrases.append(f"{t} accaparerait {fr[f'Part du risque total portée par {t}']} de tout le risque pour seulement {fr[f'Poids de {t} avec la position']} du capital [{nr}] !")
    c = d.crise
    titre, pf = fd[f"Rendement moyen de {t} ces jours-là"], fd["Rendement moyen du portefeuille actuel ces jours-là"]
    if c["rendement_moyen_titre_jours_de_crise"] < c["rendement_moyen_portefeuille_jours_de_crise"]:
        phrases.append(f"Les pires jours de marché, {t} recule en moyenne de {titre} contre {pf} pour le portefeuille [{nd}] : il amplifie les chutes au lieu d'amortir !")
    else:
        phrases.append(f"Je note que, les pires jours du portefeuille, {t} recule moins que lui : {titre} contre {pf} en moyenne [{nd}].")
    if p.filtre_esg:
        nv, fv = _faits(proces, "valeurs")
        phrases.append(f"Sur les valeurs éthiques : {fv[f'Preuves ESG collectées pour {t}']} [{nv}]. Sans preuve matérielle, le tribunal ne peut autoriser cette transaction.")
    for motif in proces.decision["contraintes"]:
        phrases.append("Violation d'une contrainte formelle : " + motif["texte"])
    return Plaidoirie("Me Austère (Le Procureur / Gouvernance)", " ".join(phrases), convoques)


def _juge_gabarit(proces) -> Plaidoirie:
    dec = proces.decision
    numeros = ", ".join(f"[{p.numero}]" for p in proces.greffier.pieces)
    motifs = dec["contraintes"] + dec["tensions"] + dec["manquants"]
    pourquoi = " ".join(m["texte"] for m in motifs) or "Aucune contrainte ni tension n'a été relevée par la règle du tribunal."
    bascules = [s["hypothese"].lower() for s in proces.salle if s["change"]]
    change = ("Le verdict changerait avec : " + " ; ".join(bascules) + "."
              if bascules else "Aucune des hypothèses testées par la salle ne change le verdict.")
    texte = (f"Le tribunal a entendu les témoins sous serment et les plaidoiries contradictoires. "
             f"VERDICT DU TRIBUNAL : {dec['verdict']}. Données auditées : pièces {numeros}, calculées sur les cours du "
             f"{proces.dossier.debut} au {proces.dossier.fin}, convertis en CAD. "
             f"Motifs de la décision : {pourquoi} Limites d'audit : cinq années de cotations observées et une seule crise majeure (2022) ; "
             f"les autres comptes demeurent inconnus. {change} "
             f"Cette décision est un avis prudentiel : l'arbitrage final appartient à l'investisseur.")
    return Plaidoirie("Le Président du Tribunal (Le Juge)", texte, [])


# ----------------------------------------------------------------------------- mode bedrock
# Valeurs vérifiées dans l'atelier AWS du Datathon (région unique : us-east-1).
# Pour itérer à faible coût : BEDROCK_MODEL_ID=global.amazon.nova-2-lite-v1:0
MODELE_PAR_DEFAUT = "global.anthropic.claude-sonnet-5"
REGION_PAR_DEFAUT = "us-east-1"


def _modele():
    from botocore.config import Config
    from strands.models import BedrockModel

    # Pas de `temperature` : Claude Sonnet 5 et Opus 5/5.5 la refusent. Ces modèles raisonnent
    # avant de répondre ; un max_tokens trop petit donne une réponse vide.
    return BedrockModel(
        model_id=os.environ.get("BEDROCK_MODEL_ID") or MODELE_PAR_DEFAUT,
        region_name=os.environ.get("AWS_REGION") or REGION_PAR_DEFAUT,
        max_tokens=2000,
        # Nouvelles tentatives avec délai croissant en cas de ThrottlingException
        boto_client_config=Config(retries={"mode": "adaptive", "max_attempts": 6}),
    )


def invoquer_claude(system_prompt: str, user_prompt: str, model_id: str | None = None) -> str:
    """Appel direct à AWS Bedrock via boto3 (API Converse). Conforme Roadmap Issue 2.1."""
    import boto3
    from botocore.config import Config

    region = os.environ.get("AWS_REGION") or REGION_PAR_DEFAUT
    client = boto3.client(
        "bedrock-runtime",
        region_name=region,
        config=Config(connect_timeout=3, read_timeout=15, retries={"mode": "adaptive", "max_attempts": 2})
    )
    mid = model_id or os.environ.get("BEDROCK_MODEL_ID") or MODELE_PAR_DEFAUT

    response = client.converse(
        modelId=mid,
        system=[{"text": system_prompt}],
        messages=[{"role": "user", "content": [{"text": user_prompt}]}],
        inferenceConfig={"maxTokens": 2000}
    )
    return response["output"]["message"]["content"][0]["text"]


def invoquer_simulateur_bedrock(proces, simu) -> str:
    """Interroge AWS Bedrock avec le prompt spécialisé de l'Agent Simulateur (ROLE_SIMULATEUR)."""
    p = proces.dossier.profil
    t = proces.dossier.ticker
    expose_simu = (
        f"Investisseur : {p.nom} ({p.resume}). Capital de départ : {dollars(simu.capital_initial)}. "
        f"Budget de perte maximal déclaré : {pct(simu.budget_perte_pct)} ({dollars(simu.budget_perte_dollars)}). "
        f"Décision examinée : allouer {pct(simu.taille, 0)} dans {t} ({simu.nom_titre}).\n\n"
        f"Faits quantitatifs de simulation certifiés :\n"
        f"1. PIRE CAS : perte de {dollars(simu.pire_cas.impact_dollars)} ({pct(simu.pire_cas.rendement_pct)}), "
        f"capital résiduel {dollars(simu.pire_cas.capital_final)}, période du {simu.pire_cas.date_debut} au {simu.pire_cas.date_fin}. "
        f"Statut : {simu.pire_cas.statut_libelle}. Δ vs sans décision : {dollars(simu.pire_cas.delta_vs_actuel_dollars)}.\n"
        f"2. CAS PROBABLE MOYEN : gain espéré de +{dollars(simu.cas_probable.impact_dollars)}/an (+{pct(simu.cas_probable.rendement_pct)}/an), "
        f"capital projeté 1 an {dollars(simu.cas_probable.capital_final)}. Δ vs sans décision : +{dollars(simu.cas_probable.delta_vs_actuel_dollars)}/an.\n"
        f"3. MEILLEUR CAS : gain max de +{dollars(simu.meilleur_cas.impact_dollars)} (+{pct(simu.meilleur_cas.rendement_pct)}), "
        f"capital projeté {dollars(simu.meilleur_cas.capital_final)}, période du {simu.meilleur_cas.date_debut} au {simu.meilleur_cas.date_fin}. "
        f"Δ vs sans décision : +{dollars(simu.meilleur_cas.delta_vs_actuel_dollars)}.\n"
        f"4. Portefeuille actuel sans décision : pire baisse {pct(simu.avant['pire_baisse_pct'])}, CAGR {pct(simu.avant['cagr_pct'])}/an."
    )
    try:
        return invoquer_claude(CONSIGNE_COMMUNE + "\n\n" + ROLE_SIMULATEUR, expose_simu)
    except Exception:
        from . import simulateur
        return simulateur.generer_deposition_simulateur(simu)


def invoquer_temoin_bedrock(proces, piece, role_systeme: str, fallback_texte: str) -> str:
    """Interroge AWS Bedrock pour faire réfléchir un témoin expert sur sa pièce scellée locale."""
    if not role_systeme:
        return fallback_texte
    p = proces.dossier.profil
    t = proces.dossier.ticker
    nom_titre = proces.dossier.donnees.univers.loc[t, "name"] if t in proces.dossier.donnees.univers.index else t

    faits_texte = "\n".join(f"- {k} : {v}" for k, v in piece.faits.items())
    user_prompt = (
        f"Investisseur : {p.nom} ({p.resume}). Capital initial : {dollars(p.capital)}. "
        f"Budget de perte max : {pct(p.budget_perte)} ({dollars(p.budget_perte * p.capital)}). Horizon : {p.horizon_ans} ans.\n"
        f"Demande examinée : allouer {pct(proces.dossier.taille, 0)} dans {t} ({nom_titre}).\n\n"
        f"DONNÉES LOCALES SCELLÉES AU GREFFE (PIÈCE [{piece.numero}]) :\n"
        f"{faits_texte}\n\n"
        f"Mission : Dépose sous serment devant le tribunal. Réfléchis et analyse l'impact concret de cette transaction "
        f"pour l'investisseur en t'appuyant STRICTEMENT sur les faits de ta pièce [{piece.numero}]. Ne prédis aucun avenir non prouvé et n'invente aucun chiffre."
    )
    try:
        return invoquer_claude(CONSIGNE_COMMUNE + "\n\n" + role_systeme, user_prompt)
    except Exception:
        return fallback_texte


def _agent_bedrock(proces, role_nom: str, role_consigne: str, message: str, avec_outil: bool) -> Plaidoirie:
    from strands import Agent, tool

    convoques: list[str] = []
    outils = []
    if avec_outil:
        convoquer = _convocateur(proces, role_nom, convoques)
        liste = "; ".join(f"{nom} ({desc})" for nom, desc in temoins.DESCRIPTIONS.items())

        @tool
        def convoquer_temoin(nom: str) -> str:
            """Convoque un témoin et retourne sa déposition sous forme de pièce numérotée.

            Args:
                nom: nom du témoin à convoquer, parmi : risque, diversification, valeurs, macro.
            """
            return convoquer(nom)

        convoquer_temoin.__doc__ = (convoquer_temoin.__doc__ or "") + f"\nTémoins : {liste}"
        outils = [convoquer_temoin]
    agent = Agent(model=_modele(), system_prompt=CONSIGNE_COMMUNE + "\n\n" + role_consigne,
                  tools=outils, callback_handler=None)
    resultat = agent(message)
    return Plaidoirie(role_nom, str(resultat).strip(), convoques)


def _convoquer_d_office(proces) -> None:
    """Le greffier s'assure qu'une pièce existe pour chaque motif utilisé par la règle."""
    dec = proces.decision
    requis = {"risque"} | {m["temoin"] for m in dec["contraintes"] + dec["tensions"] + dec["manquants"]}
    for nom in sorted(requis):
        temoins.TEMOINS[nom](proces.dossier, proces.greffier, "le Greffier, d'office")


def plaider(proces) -> None:
    expose = _expose(proces)
    if proces.mode == "bedrock":
        try:
            defense = _agent_bedrock(proces, "La Défense", ROLE_DEFENSE, expose, True)
            procureur = _agent_bedrock(
                proces, "Le Procureur", ROLE_PROCUREUR,
                expose + "\n\nPlaidoirie de la Défense :\n" + defense.texte, True)
            _convoquer_d_office(proces)
            pieces = "\n\n".join(p.en_texte() for p in proces.greffier.pieces)
            salle = "\n".join(f"- {s['hypothese']} : {s['verdict']}" for s in proces.salle)
            dec = proces.decision
            motifs = "\n".join("- " + m["texte"] for m in dec["contraintes"] + dec["tensions"] + dec["manquants"])
            juge = _agent_bedrock(
                proces, "Le Juge", ROLE_JUGE,
                f"{expose}\n\nVERDICT FIXÉ PAR LA RÈGLE : {dec['verdict']}\nMotifs de la règle :\n{motifs or '- aucun'}"
                f"\n\nPIÈCES :\n{pieces}\n\nLA SALLE (une hypothèse changée à la fois) :\n{salle}"
                f"\n\nDéfense : {defense.texte}\n\nProcureur : {procureur.texte}", False)
        except Exception as erreur:  # identifiants AWS absents, modèle non activé, réseau...
            proces.avertissement = (f"Appel à Bedrock impossible ({type(erreur).__name__} : {erreur}). "
                                    "Le procès a été rejoué en mode gabarit.")
            proces.mode = "gabarit"
            proces.greffier.pieces.clear()
            return plaider(proces)
    else:
        defense = _defense_gabarit(proces)
        procureur = _procureur_gabarit(proces)
        _convoquer_d_office(proces)
        juge = _juge_gabarit(proces)

    for plaidoirie in (defense, procureur, juge):
        plaidoirie.non_verifies = proces.greffier.verifier(plaidoirie.texte)
    proces.plaidoiries = [defense, procureur]
    proces.motivation = juge


# ----------------------------------------------------------------------------- Agent Vulgarisateur (Analogies)

ROLE_VULGARISATEUR = """Tu es l'Interprète du Juré (Le Médiateur Vulgarisateur) au tribunal de « Règlement de comptes ».
Ton rôle est de traduire les arguments financiers ou juridiques complexes entendus à l'audience en une ANALOGIE CONCRÈTE, INTUITIVE et IMAGÉE de la vie courante (par exemple : conduite automobile, météo/navigation maritime, cuisine, sport, mécanique, santé/randonnée).

Consignes strictes :
- Développe UNE SEULE analogie percutante et facile à comprendre pour un profane.
- Sois fidèle à la réalité du risque : si le texte évoque une forte perte ou un danger, l'analogie doit faire ressentir ce risque sans l'atténuer ni dramatiser.
- Adopte un ton bienveillant, direct et pédagogique.
- Ne donne aucun conseil financier d'achat ou de vente, et ne promets aucun rendement.
- Reste concis : entre 50 et 90 mots maximum.
- Réponds directement par l'analogie sans formule d'introduction pompeuse (commence par exemple par : « C'est un peu comme... », « Imaginez que... » ou « Voyez cela comme... »)."""


def analogies_statiques(texte: str, acteur: str | None = None) -> str:
    """Fournit une analogie pédagogique contextuelle certifiée sans appel réseau."""
    t = (texte or "").lower()
    
    if any(k in t for k in ["var", "value at risk", "shortfall", "cvar", "extrême", "queue"]):
        return (
            "Imaginez un airbag : la Value at Risk vous indique l'impact maximal encaissé dans 95 % des "
            "trajets quotidiens. Mais l'Expected Shortfall vous prévient de la violence du choc dans les 5 % "
            "d'accidents les plus destructeurs, là où l'airbag ne suffit plus à empêcher les dégâts."
        )
    elif any(k in t for k in ["sharpe", "prime de risque"]):
        return (
            "C'est comme comparer deux voitures de rallye : le ratio de Sharpe ne mesure pas seulement la vitesse "
            "de pointe (le rendement espéré), mais surtout à quel point le véhicule tremble, dérape et surchauffe "
            "(le risque) pour atteindre cette vitesse."
        )
    elif any(k in t for k in ["baisse", "creux", "budget", "perte", "sommet", "chute"]):
        return (
            "C'est comme escalader une paroi rocheuse avec une corde de rappel : la pire baisse pic-au-creux "
            "mesure la profondeur maximale du vide sous vos pieds. Si ce gouffre dépasse la longueur de votre corde "
            "(votre budget de perte toléré), vous risquez le décrochage fatal."
        )
    elif any(k in t for k in ["bêta", "beta", "sensibilité"]):
        return (
            "Le Bêta, c'est comme attacher votre bicyclette derrière un camion lancé sur l'autoroute. "
            "Quand le camion accélère, vous filez à toute allure ; mais au premier coup de frein brutal, "
            "l'impact est bien plus violent pour vous que pour la remorque."
        )
    elif any(k in t for k in ["diversif", "secteur", "tempête", "choc", "panier"]):
        return (
            "C'est la règle d'or du panier d'œufs : si vous mettez tous vos œufs dans un seul panier en osier "
            "et qu'il vous glisse des mains, tout s'écrase. Répartir vos provisions dans des sacs différents "
            "garantit que vous ne dormirez jamais l'estomac vide après une maladresse."
        )
    elif any(k in t for k in ["esg", "valeur", "morale", "éthique", "gouvernance"]):
        return (
            "C'est comme réserver une table au restaurant : vous ne vérifiez pas seulement si le plat est bon marché "
            "et copieux, vous voulez aussi vous assurer que la cuisine est propre et que les cuisiniers sont traités "
            "équitablement avant d'y inviter vos proches."
        )
    elif any(k in t for k in ["macro", "taux", "banque", "inflation", "boc"]):
        return (
            "Les taux d'intérêt agissent comme la force de gravité : quand la banque centrale monte les taux, "
            "la pesanteur devient plus lourde pour tout le monde. Les entreprises et les investissements ont alors "
            "beaucoup plus de mal à décoller et à rester en l'air."
        )
    else:
        return (
            "Voyez cela comme une traversée en voilier : par mer calme, gonfler la grand-voile vous fait gagner "
            "du temps, mais si la météo vire à l'orage, vous devez vous assurer d'avoir de solides gilets de sauvetage "
            "pour ne pas chavirer sous la première rafale imprévue."
        )


def generer_analogie(texte: str, acteur: str | None = None, role: str | None = None, mode: str = "bedrock") -> dict:
    """Génère une analogie simplifiée pour vulgariser une réplique ou une déposition technique."""
    if not texte or not texte.strip():
        return {
            "analogie": "Il n'y a pas assez de matière technique ici pour formuler une analogie.",
            "source": "statique",
        }

    if mode == "bedrock":
        user_prompt = (
            f"Intervention prononcée par {acteur or 'un intervenant'} ({role or 'au tribunal'}) :\n"
            f"« {texte.strip()} »\n\n"
            f"Consigne : Traduis cette explication technique en une analogie concrète, percutante et accessible "
            f"pour un investisseur ordinaire."
        )
        try:
            analogie = invoquer_claude(CONSIGNE_COMMUNE + "\n\n" + ROLE_VULGARISATEUR, user_prompt)
            if analogie and len(analogie.strip()) > 20:
                return {"analogie": analogie.strip(), "source": "bedrock"}
        except Exception:
            pass  # repli gracieux sans lever d'erreur

    return {"analogie": analogies_statiques(texte, acteur), "source": "gabarit"}

