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
    return (f"Investisseur fictif : {p.nom}. {p.resume} Objectif : {p.objectif} "
            f"Préférences : {p.preferences} Capital : {dollars(p.capital)}. "
            f"Demande : placer {pct(d.taille, 0)} du portefeuille dans {d.ticker} "
            f"({d.donnees.univers.loc[d.ticker, 'name']}), financé au prorata des autres positions.")


def _faits(proces, temoin: str) -> tuple[str, dict]:
    for piece in proces.greffier.pieces:
        if piece.temoin == temoin:
            return piece.numero, piece.faits
    raise KeyError(temoin)


# ----------------------------------------------------------------------------- mode gabarit
def _defense_gabarit(proces) -> Plaidoirie:
    d, p, t = proces.dossier, proces.dossier.profil, proces.dossier.ticker
    convoques: list[str] = []
    _convocateur(proces, "la Défense", convoques)("risque")
    n, f = _faits(proces, "risque")
    objectif = p.objectif[0].lower() + p.objectif[1:].rstrip(".")
    phrases = [f"{p.nom} déclare l'objectif suivant : {objectif}. La demande reste limitée à "
               f"{f[f'Poids de {t} avec la position']} du portefeuille [{n}]."]
    if d.apres["pire_baisse"]["recupere"] and d.apres["pire_baisse"]["annees_sous_le_sommet"] <= p.horizon_ans:
        phrases.append(f"Dans le passé observé, le portefeuille avec la position est revenu à son sommet après "
                       f"{f['Temps passé sous le sommet, avec la position']} [{n}], moins que l'horizon de "
                       f"{annees(p.horizon_ans)}.")
    avant, apres = f["Pire baisse observée, portefeuille actuel"], f["Pire baisse observée, avec la position"]
    if d.apres["pire_baisse"]["profondeur"] >= d.avant["pire_baisse"]["profondeur"]:
        phrases.append(f"La pire baisse observée ne s'aggrave pas : elle passe de {avant} à {apres} [{n}]. "
                       f"Je reconnais la limite : cinq ans de données ne contiennent qu'une seule grande crise.")
    else:
        phrases.append(f"Je reconnais la limite : la pire baisse observée passe de {avant} à {apres} [{n}], "
                       f"et ces chiffres reposent sur une période où {t} a fini par remonter, ce que rien ne garantit.")
    return Plaidoirie("La Défense", " ".join(phrases), convoques)


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
    phrases = []
    budget = fr["Budget de perte déclaré (hypothèse du profil)"]
    avant = fr["Perte en dollars au pire creux, portefeuille actuel"]
    apres = fr["Perte en dollars au pire creux, avec la position"]
    if d.apres["pire_baisse"]["profondeur"] < d.avant["pire_baisse"]["profondeur"]:
        phrases.append(f"Au pire creux, la perte passerait de {avant} à {apres}, pour un budget de perte "
                       f"déclaré de {budget} [{nr}].")
    else:
        phrases.append(f"Je ne conteste pas le risque de perte : au pire creux, elle passerait de {avant} à "
                       f"{apres}, pour un budget déclaré de {budget} [{nr}].")
    part = d.apres["contributions_risque"].get(t, 0.0)
    if part > d.apres["poids"].get(t, 0.0):
        phrases.append(f"{t} porterait {fr[f'Part du risque total portée par {t}']} du risque total pour "
                       f"{fr[f'Poids de {t} avec la position']} du portefeuille [{nr}].")
    c = d.crise
    titre, pf = fd[f"Rendement moyen de {t} ces jours-là"], fd["Rendement moyen du portefeuille actuel ces jours-là"]
    if c["rendement_moyen_titre_jours_de_crise"] < c["rendement_moyen_portefeuille_jours_de_crise"]:
        phrases.append(f"Les pires jours du portefeuille, {t} recule en moyenne de {titre} contre {pf} "
                       f"pour le portefeuille [{nd}] : il n'amortit pas les baisses.")
    else:
        phrases.append(f"Je reconnais que, les pires jours du portefeuille, {t} recule moins que lui : "
                       f"{titre} contre {pf} en moyenne [{nd}].")
    if p.filtre_esg:
        nv, fv = _faits(proces, "valeurs")
        phrases.append(f"Sur les valeurs, le témoin dépose : {fv[f'Preuves ESG collectées pour {t}']} [{nv}]. "
                       f"Sans preuve, le tribunal ne peut pas conclure que la demande respecte les valeurs déclarées.")
    for motif in proces.decision["contraintes"]:
        phrases.append("Contrainte déclarée : " + motif["texte"])
    return Plaidoirie("Le Procureur", " ".join(phrases), convoques)


def _juge_gabarit(proces) -> Plaidoirie:
    dec = proces.decision
    numeros = ", ".join(f"[{p.numero}]" for p in proces.greffier.pieces)
    motifs = dec["contraintes"] + dec["tensions"] + dec["manquants"]
    pourquoi = " ".join(m["texte"] for m in motifs) or "Aucune contrainte ni tension n'a été relevée par la règle du tribunal."
    bascules = [s["hypothese"].lower() for s in proces.salle if s["change"]]
    change = ("Le verdict changerait avec : " + " ; ".join(bascules) + "."
              if bascules else "Aucune des hypothèses testées par la salle ne change le verdict.")
    texte = (f"Verdict : {dec['verdict']}. Données : pièces {numeros}, calculées sur les prix du "
             f"{proces.dossier.debut} au {proces.dossier.fin}, convertis en dollars canadiens. "
             f"Motifs : {pourquoi} Limites : cinq ans de données et une seule grande crise observée ; "
             f"les autres comptes de l'investisseur sont inconnus ; les montants du profil sont des hypothèses. "
             f"{change} Ceci est une simulation : la décision appartient à l'investisseur.")
    return Plaidoirie("Le Juge", texte, [])


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
