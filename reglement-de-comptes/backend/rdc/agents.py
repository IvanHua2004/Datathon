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
            f"({d.donnees.univers.loc[d.ticker, 'name']}), financé au prorata des autres positions.")


def _faits(proces, temoin: str) -> tuple[str, dict]:
    for piece in proces.greffier.pieces:
        if piece.temoin == temoin:
            return piece.numero, piece.faits
    raise KeyError(temoin)


# ----------------------------------------------------------------------------- mode gabarit
def depositions_temoins_incarnee(proces) -> list[dict]:
    """Chaque témoin dépose sous serment à la barre sous forme de personnage incarné."""
    resultats = []
    d, p, t = proces.dossier, proces.dossier.profil, proces.dossier.ticker

    for piece in proces.greffier.pieces:
        f = piece.faits
        n = piece.numero
        if piece.temoin == "risque":
            texte = (f"Monsieur le Président, je dépose sous serment la pièce [{n}]. L'analyse de 1 304 séances "
                     f"démontre que la pire baisse du portefeuille passerait de {f['Pire baisse observée, portefeuille actuel']} "
                     f"à {f['Pire baisse observée, avec la position']} (soit {f['Perte en dollars au pire creux, avec la position']} "
                     f"pour un budget déclaré de {f['Budget de perte déclaré (hypothèse du profil)']}). "
                     f"Le titre {t} porterait à lui seul {f[f'Part du risque total portée par {t}']} du risque global.")
            resultats.append({
                "temoin": "risque",
                "personnage": "Dr. Laurent (Expert Actuaire)",
                "role": "Témoin du Risque",
                "piece": n,
                "texte": texte
            })
        elif piece.temoin == "diversification":
            titre_crise = f.get(f"Rendement moyen de {t} ces jours-là", "N/A")
            pf_crise = f.get("Rendement moyen du portefeuille actuel ces jours-là", "N/A")
            texte = (f"À la barre, je verse la pièce [{n}] au dossier. Lors des 10 % pires jours de tempête boursière, "
                     f"{t} affiche un rendement moyen de {titre_crise} contre {pf_crise} pour le reste du portefeuille. "
                     f"L'exposition au secteur {f.get(f'Secteur de {t} (étiquette des organisateurs)', 'Inconnu')} passerait à "
                     f"{f.get(f'Poids du secteur {d.secteur}, avec la position', 'N/A')}.")
            resultats.append({
                "temoin": "diversification",
                "personnage": "Mme Chantal (Cartographe de Portefeuille)",
                "role": "Témoin de la Diversification",
                "piece": n,
                "texte": texte
            })
        elif piece.temoin == "valeurs":
            texte = (f"En tant qu'auditeur de conformité ESG, je dépose la pièce [{n}]. Nos investigations publiques "
                     f"attestent : {f.get(f'Preuves ESG collectées pour {t}', 'aucune preuve')}. Le respect des exigences morales de {p.nom} "
                     f"dépend strictement de ces éléments factuels.")
            resultats.append({
                "temoin": "valeurs",
                "personnage": "Me Tremblay (Auditeur ESG & Gouvernance)",
                "role": "Témoin des Valeurs",
                "piece": n,
                "texte": texte
            })
        elif piece.temoin == "macro":
            texte = (f"J'atteste sous serment des conditions macroéconomiques via la pièce [{n}]. Lors de la pire baisse "
                     f"du sommet au creux, la hausse brutale des taux d'intérêt et l'inflation ont brisé les corrélations habituelles.")
            resultats.append({
                "temoin": "macro",
                "personnage": "M. Raymond (Observateur des Banques Centrales)",
                "role": "Témoin Macroéconomie",
                "piece": n,
                "texte": texte
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
    if p.filtre_esg:
        convoquer("valeurs")
    if p.horizon_ans <= 5:
        convoquer("macro")
    nr, fr = _faits(proces, "risque")
    nd, fd = _faits(proces, "diversification")
    phrases = ["Objection véhémente, Votre Honneur ! Mon rôle de procureur est de protéger l'investisseur contre l'aveuglement."]
    budget = fr["Budget de perte déclaré (hypothèse du profil)"]
    avant = fr["Perte en dollars au pire creux, portefeuille actuel"]
    apres = fr["Perte en dollars au pire creux, avec la position"]
    if d.apres["pire_baisse"]["profondeur"] < d.avant["pire_baisse"]["profondeur"]:
        phrases.append(f"Les chiffres ne mentent pas : au pire creux, la perte bondirait de {avant} à {apres}, pour un budget de perte déclaré de seulement {budget} [{nr}] !")
    else:
        phrases.append(f"Au pire creux, la perte atteindrait {apres}, pour un budget déclaré de {budget} [{nr}].")
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
        config=Config(retries={"mode": "adaptive", "max_attempts": 6})
    )
    mid = model_id or os.environ.get("BEDROCK_MODEL_ID") or MODELE_PAR_DEFAUT

    response = client.converse(
        modelId=mid,
        system=[{"text": system_prompt}],
        messages=[{"role": "user", "content": [{"text": user_prompt}]}],
        inferenceConfig={"maxTokens": 2000}
    )
    return response["output"]["message"]["content"][0]["text"]


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
