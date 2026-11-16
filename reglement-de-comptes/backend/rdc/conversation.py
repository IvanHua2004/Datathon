"""Ce qui rend le dialogue naturel autour du tribunal, sans jamais inventer de chiffre.

- politesse : bonjour, merci, au revoir, recommencer;
- fautes de frappe sur les titres (« nvidai » -> NVIDIA), dites à l'investisseur;
- questions sur son propre dossier (« qu'est-ce que j'ai dans mon portefeuille ? »);
- définitions des mots du tribunal (« c'est quoi la volatilité ? »), écrites à la main;
- en dernier recours, Bedrock classe une question que les règles n'ont pas comprise et
  la réécrit en question simple, que les règles traitent ensuite. Le modèle ne choisit
  jamais un titre hors des 31 actifs et ne produit aucun chiffre.
"""
from __future__ import annotations

import difflib
import json
import os
import re

# --------------------------------------------------------------------------- politesse
SALUTATION = r"^(?:bonjour|bonsoir|salut|allo|coucou|hello|hey|hi|yo)\b"
REMERCIEMENT = r"\b(?:merci|thanks|parfait|super|genial|top)\b"
AU_REVOIR = r"\b(?:au revoir|bye|a plus|a bientot|bonne (?:journee|soiree))\b"
RECOMMENCER = (r"^(?:annule|annuler|recommence|recommencer|reset|efface|effacer|on recommence|"
               r"nouvelle (?:question|conversation)|oublie (?:tout|ca))\b")


def politesse(norm: str, nom: str) -> tuple[str, str] | None:
    """(motif, message) pour une formule de politesse courte, sinon None."""
    court = len(norm.split()) <= 5
    if re.search(RECOMMENCER, norm):
        return "recommencer", ("C'est noté, j'efface le contexte. Quelle décision voulez-vous "
                               "soumettre au tribunal ?")
    if court and re.search(SALUTATION, norm):
        return "salutation", (f"Bonjour {nom} ! Je suis le greffier. Posez-moi une décision à juger "
                              "(« 10 % dans NVDA ? »), demandez les chiffres d'un titre, ou comparez-en deux.")
    if court and re.search(AU_REVOIR, norm):
        return "au_revoir", "Au revoir ! L'audience est levée. Revenez quand vous voulez."
    if court and re.search(REMERCIEMENT, norm):
        return "remerciement", "Avec plaisir. Une autre décision à soumettre au tribunal ?"
    return None


# --------------------------------------------------------------------------- fautes de frappe
# Mots fréquents des questions, à ne jamais prendre pour un titre mal écrit.
MOTS_COURANTS = set("""
placer placement portefeuille devrais devrait pourrais acheter investir ajouter mettre garder vendre
actions action titres titre compare comparer comparaison moyenne obligations obligation crypto
chiffres stats statistiques donnees performance rendement volatilite risque profil budget horizon
capital proteger prudent plutot pourquoi comment combien quelle quelles quels lequel laquelle
montre montrer donne donner explique expliquer definition marche marches canada canadien
canadiennes americain americaines secteur secteurs technologie energie banque banques sante
dividende dividendes indice fonds bourse argent epargne retraite annee annees mois jours debat
tribunal greffier archiviste juge verdict avocat defense procureur temoin entre contre avec
""".split())


def _vocabulaire(univers: dict[str, str], alias: dict[str, tuple[str, ...]]) -> dict[str, str]:
    """mot -> ticker, pour les noms et symboles d'un seul mot."""
    vocab: dict[str, str] = {}
    for ticker, nom in univers.items():
        mots = [ticker.lower().split(".")[0].split("-")[0], *alias.get(ticker, ())]
        mots += [m for m in re.split(r"[\s(),&]+", _norm(nom)) if len(m) >= 5]
        for m in mots:
            if len(m) >= 4 and " " not in m and m not in MOTS_COURANTS:
                vocab.setdefault(m, ticker)
    return vocab


def _norm(texte: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return t.lower().replace("’", "'")


def titres_approchants(norm: str, univers: dict[str, str],
                       alias: dict[str, tuple[str, ...]]) -> list[tuple[str, str]]:
    """[(mot tapé, ticker)] pour les mots qui ressemblent beaucoup à un titre connu."""
    vocab = _vocabulaire(univers, alias)
    trouves: list[tuple[str, str]] = []
    for mot in re.findall(r"[a-z][a-z.\-]{3,}", norm):
        if mot in MOTS_COURANTS or mot in vocab:
            continue
        proche = difflib.get_close_matches(mot, vocab.keys(), n=1, cutoff=0.8)
        if proche and vocab[proche[0]] not in [t for _, t in trouves]:
            trouves.append((mot, vocab[proche[0]]))
    return trouves


# --------------------------------------------------------------------------- le dossier de l'investisseur
QUESTION_PROFIL = (
    r"\bmon (?:portefeuille|profil|budget|horizon|objectif|capital|plafond|risque|dossier)\b",
    r"\bma (?:tolerance|limite|perte|situation|strategie)\b",
    r"\bmes (?:titres|placements|positions|contraintes|preferences|actifs|actions|objectifs)\b",
    r"qu'?est-ce que j'?ai\b", r"\bqu'?ai-je\b", r"\bqui suis-je\b", r"\bj'?ai quoi\b",
    r"\bcombien j'?ai\b", r"\bje possede\b", r"\bpourquoi (?:je |j'|ai-je |suis-je )?(?:ne )?(?:peux|peut|ai|suis) pas\b",
)


def question_sur_le_profil(norm: str) -> bool:
    return any(re.search(m, norm) for m in QUESTION_PROFIL)


# --------------------------------------------------------------------------- glossaire
DEMANDE_DE_DEFINITION = (
    r"\bc'?est quoi\b", r"\bqu'?est-ce qu(?:e|')?(?:c'?est|un|une|la|le|l')?", r"\bque veut dire\b",
    r"\bveut dire quoi\b", r"\bca veut dire\b", r"\bdefini", r"\bexplique", r"\bsignifie",
    r"\bpourquoi\b.*\bverdict\b", r"\bc'?est quoi\b",
)

GLOSSAIRE: dict[str, tuple[tuple[str, ...], str]] = {
    "volatilité": ((r"volatil",),
                   "La volatilité mesure l'ampleur habituelle des variations d'un placement sur un an. "
                   "Plus elle est haute, plus la valeur monte et descend fortement, dans les deux sens."),
    "pire baisse": ((r"pire baisse", r"drawdown", r"perte maximale"),
                    "La pire baisse est la plus forte chute observée entre un sommet et le creux qui suit. "
                    "Elle dit combien on aurait pu perdre au pire moment, et le temps pour revenir au sommet."),
    "budget de perte": ((r"budget de perte", r"tolerance", r"perte (?:supportable|acceptable)"),
                        "Le budget de perte est la baisse maximale que l'investisseur dit pouvoir supporter. "
                        "Le tribunal compare la pire baisse du portefeuille à ce budget."),
    "rendement annualisé": ((r"rendement annualise", r"annualis", r"rendement moyen", r"\brendement\b"),
                            "Le rendement annualisé est la croissance moyenne par an qui donnerait le même "
                            "résultat final. Il lisse les bonnes et les mauvaises années."),
    "FNB": ((r"\bfnb\b", r"\betf\b", r"fonds negocie"),
            "Un FNB (fonds négocié en bourse, ETF en anglais) est un panier de titres qu'on achète en une "
            "seule fois, comme une action. SPY contient par exemple les 500 plus grandes entreprises américaines."),
    "obligation": ((r"obligation", r"\bbonds?\b"),
                   "Une obligation est un prêt à un État ou à une entreprise, qui verse des intérêts. "
                   "Elle varie en général moins que les actions, mais elle baisse quand les taux montent."),
    "action": ((r"c'?est quoi une action", r"qu'?est-ce qu'?une action"),
               "Une action est une part d'une entreprise. Sa valeur suit les résultats et les attentes "
               "sur cette entreprise, et peut varier fortement."),
    "diversification": ((r"diversif",),
                        "Diversifier, c'est répartir son argent entre des placements qui ne bougent pas "
                        "tous ensemble, pour que la chute de l'un pèse moins sur l'ensemble."),
    "part du risque": ((r"part du risque", r"contribution au risque"),
                       "La part du risque est la portion des variations du portefeuille qui vient d'un "
                       "seul titre. Un petit titre très volatil peut porter une grande part du risque."),
    "horizon": ((r"\bhorizon\b",),
                "L'horizon est le temps avant d'avoir besoin de l'argent. Plus il est long, plus on a "
                "le temps de se remettre d'une baisse."),
    "cryptoactif": ((r"crypto",),
                    "Un cryptoactif (Bitcoin, Ether) est une monnaie numérique sans banque centrale. "
                    "Ses variations sont parmi les plus fortes de tout le jeu de données."),
    "ESG": ((r"\besg\b",),
            "ESG veut dire environnement, social et gouvernance : des critères pour écarter les "
            "entreprises jugées controversées sur ces sujets."),
    "dividende": ((r"dividende",),
                  "Un dividende est la part des profits qu'une entreprise verse à ses actionnaires. "
                  "Les prix ajustés du jeu de données en tiennent compte."),
    "verdict « contraire à une contrainte »": ((r"contraire", r"contrainte"),
        "« Contraire à une contrainte déclarée » : la décision enfreint une règle que l'investisseur a "
        "lui-même posée (classe d'actifs exclue, budget de perte dépassé, plafond par titre)."),
    "verdict « en tension »": ((r"en tension", r"\btension\b"),
        "« En tension avec le profil » : aucune règle n'est enfreinte, mais la décision tire le "
        "portefeuille vers plus de risque ou de concentration que le profil ne le suggère."),
    "verdict « compatible »": ((r"\bcompatible\b",),
        "« Compatible avec le profil » : la décision respecte les contraintes déclarées et ne crée pas "
        "de tension notable avec l'objectif, l'horizon ou la tolérance au risque."),
    "verdict « indécidable »": ((r"indecidable",),
        "« Indécidable » : il manque une information pour trancher, par exemple une preuve ESG pour un "
        "secteur que l'investisseur veut éviter."),
    "duel": ((r"\bduel\b",),
             "Le duel oppose deux titres sur le même profil : deux procès, deux avocats, puis une règle "
             "fixe tranche (verdict le moins grave, puis plus petite pire baisse)."),
}


def terme_demande(norm: str, a_des_titres: bool) -> str | None:
    """Le terme du glossaire demandé, si la question est une demande de définition."""
    if a_des_titres:
        return None
    if not any(re.search(m, norm) for m in DEMANDE_DE_DEFINITION):
        return None
    for terme, (motifs, _) in GLOSSAIRE.items():
        if any(re.search(m, norm) for m in motifs):
            return terme
    return None


def exemple_pour(terme: str, profil: dict | None) -> str | None:
    if not profil:
        return None
    nom = profil["nom"]
    if terme == "budget de perte":
        return f"Pour {nom}, le budget de perte déclaré est de {round(profil['budgetPerte'] * 100):g} %."
    if terme == "horizon":
        return f"Pour {nom}, l'horizon déclaré est d'environ {profil['horizonAns']:g} ans."
    if terme == "cryptoactif" and "crypto" in profil.get("classesExclues", []):
        return f"{nom} exclut les cryptoactifs : un placement en crypto sera jugé contraire à son profil."
    if terme == "ESG" and profil.get("filtreEsg"):
        return f"{nom} applique un filtre ESG : le secteur de l'énergie demande une preuve avant d'entrer."
    return None


# --------------------------------------------------------------------------- Bedrock en dernier recours
INTENTIONS = ("decision", "chiffres", "comparaison", "profil", "definition", "catalogue", "hors_sujet")


def classer_avec_modele(texte: str, univers: dict[str, str], resume_profil: str,
                        historique: list[str], votes_precedents: str = "") -> dict | None:
    """Demande à Bedrock de classer une question que les règles n'ont pas comprise.

    Renvoie {"intention", "tickers", "part", "terme"} validé, ou None (désactivé, indisponible,
    réponse inutilisable). RDC_GREFFIER_MODELE=0 le désactive (tests).
    """
    if os.environ.get("RDC_GREFFIER_MODELE", "1") == "0":
        return None
    try:
        import boto3
        from botocore.config import Config

        from .agents import MODELE_PAR_DEFAUT, REGION_PAR_DEFAUT

        client = boto3.client(
            "bedrock-runtime", region_name=os.environ.get("AWS_REGION") or REGION_PAR_DEFAUT,
            config=Config(connect_timeout=5, read_timeout=25, retries={"max_attempts": 2}),
        )
        liste = "\n".join(f"- {t} : {n}" for t, n in univers.items())
        avant = "\n".join(f"- {h}" for h in historique) or "- (aucun)"
        consigne = (
            "Tu es le greffier d'un tribunal financier simulé. Classe la question de l'investisseur "
            "fictif. Intentions possibles : decision (placer une part dans un ou plusieurs titres), "
            "chiffres (données d'un titre), comparaison (deux titres côte à côte), profil (son propre "
            "dossier), definition (un mot de finance), catalogue (la liste des titres), hors_sujet. "
            "Choisis les titres UNIQUEMENT dans la liste ; maximum 4. La part est une fraction entre "
            "0,02 et 0,5, ou null si elle n'est pas dite. Tiens compte des questions précédentes, la "
            "plus récente en priorité. Réponds seulement en JSON : "
            '{"intention": "...", "tickers": ["..."], "part": null, "terme": null}\n\n'
            f"Profil : {resume_profil}\nQuestions précédentes :\n{avant}\n"
            f"Votes des débats précédents :\n{votes_precedents or '- (aucun)'}\nTitres disponibles :\n{liste}"
        )
        reponse = client.converse(
            modelId=os.environ.get("BEDROCK_MODEL_ID") or MODELE_PAR_DEFAUT,
            system=[{"text": consigne}],
            messages=[{"role": "user", "content": [{"text": texte[:500]}]}],
            inferenceConfig={"maxTokens": 2000},
        )
        bloc = "".join(c.get("text", "") for c in reponse["output"]["message"]["content"])
        brut = json.loads(bloc[bloc.index("{"): bloc.rindex("}") + 1])
    except Exception:
        return None
    intention = brut.get("intention")
    if intention not in INTENTIONS:
        return None
    tickers = [t for t in brut.get("tickers") or [] if t in univers][:4]
    part = brut.get("part")
    part = float(part) if isinstance(part, (int, float)) and 0.02 <= float(part) <= 0.5 else None
    terme = brut.get("terme") if isinstance(brut.get("terme"), str) else None
    return {"intention": intention, "tickers": tickers, "part": part, "terme": terme}


def question_canonique(classement: dict) -> str | None:
    """Réécrit le classement du modèle en question simple, que les règles savent traiter."""
    i, t, p = classement["intention"], classement["tickers"], classement["part"]
    if i == "decision" and len(t) == 1:
        return f"Devrais-je placer {round(p * 100):g} % dans {t[0]} ?" if p else f"Que penses-tu de {t[0]} ?"
    if i == "chiffres" and t:
        return f"Les chiffres de {t[0]}"
    if i == "comparaison" and len(t) >= 2:
        return f"Compare {t[0]} et {t[1]}"
    if i == "profil":
        return "Qu'est-ce que j'ai dans mon portefeuille ?"
    if i == "definition" and classement["terme"]:
        return f"C'est quoi {classement['terme']} ?"
    if i == "catalogue":
        return "Liste des actifs"
    return None
