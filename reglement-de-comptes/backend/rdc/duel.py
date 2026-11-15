"""Le duel : deux procès sur le même profil, puis une décision A contre B.

Chaque dossier passe devant le tribunal comme d'habitude (témoins, plaidoiries, juge).
La décision du duel suit une règle fixe, comme le verdict :
  1. le verdict le moins grave l'emporte
     (compatible < indécidable < en tension < contraire à une contrainte);
  2. à verdict égal, la pire baisse du portefeuille la plus faible l'emporte;
  3. si l'écart est inférieur à 0,5 point, c'est une égalité.
Les agents argumentent; la règle tranche. Ce n'est pas un conseil financier.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

from .format import pct
from .proces import V_COMPATIBLE, V_CONTRAINTE, V_INDECIDABLE, V_TENSION, ouvrir_proces
from .profils import Profil

GRAVITE = {V_COMPATIBLE: 0, V_INDECIDABLE: 1, V_TENSION: 2, V_CONTRAINTE: 3}
ECART_EGALITE = 0.005


def _cote(p) -> dict:
    d = p.dossier
    apres, avant = d.apres, d.avant
    budget = -d.profil.budget_perte
    pire = apres["pire_baisse"]["profondeur"]
    part_risque = apres["contributions_risque"].get(d.ticker, 0.0)
    motifs = [m["texte"] for cle in ("contraintes", "tensions", "manquants") for m in p.decision[cle]]
    r = d.donnees.rendements[d.ticker]
    annualise = float((1 + r).prod() ** (252 / len(r)) - 1)
    return {
        "ticker": d.ticker,
        "nomTitre": str(d.donnees.univers.loc[d.ticker, "name"]),
        "taille": d.taille,
        "verdict": p.decision["verdict"],
        "gravite": GRAVITE.get(p.decision["verdict"], 1),
        "motifs": motifs,
        "juge": p.motivation.texte if p.motivation else "",
        "defense": p.plaidoiries[0].texte if p.plaidoiries else "",
        "procureur": p.plaidoiries[1].texte if len(p.plaidoiries) > 1 else "",
        "avertissement": p.avertissement,
        "mode": p.mode,
        "chiffres": [
            {"libelle": "Pire baisse du portefeuille", "valeur": pct(pire),
             "avant": pct(avant["pire_baisse"]["profondeur"]), "alerte": pire < budget},
            {"libelle": "Budget de perte déclaré", "valeur": pct(budget), "avant": pct(budget), "alerte": False},
            {"libelle": "Volatilité annuelle", "valeur": pct(apres["volatilite_annuelle"]),
             "avant": pct(avant["volatilite_annuelle"]), "alerte": False},
            {"libelle": "Résultat en 2022", "valeur": pct(apres["rendement_2022"]),
             "avant": pct(avant["rendement_2022"]), "alerte": False},
            {"libelle": "Part du risque due au titre", "valeur": pct(part_risque), "avant": "—",
             "alerte": part_risque > 0.25},
            {"libelle": "Rendement annuel moyen du titre seul", "valeur": pct(annualise), "avant": "—",
             "alerte": False},
        ],
        "_pire": pire,
        "_mesures": {"pire": pire, "vol": apres["volatilite_annuelle"], "an2022": apres["rendement_2022"],
                     "risque": part_risque, "croissance": annualise},
    }


def decider(a: dict, b: dict) -> dict:
    if a["gravite"] != b["gravite"]:
        g, p = (a, b) if a["gravite"] < b["gravite"] else (b, a)
        raison = (f"son verdict est moins grave : « {g['verdict']} » contre « {p['verdict']} »")
        return {"gagnant": g["ticker"], "raison": raison, "regle": 1}
    ecart = a["_pire"] - b["_pire"]
    if abs(ecart) < ECART_EGALITE:
        return {"gagnant": None, "regle": 3,
                "raison": "verdicts identiques et pires baisses du portefeuille presque égales "
                          f"({pct(a['_pire'])} contre {pct(b['_pire'])})"}
    g, p = (a, b) if ecart > 0 else (b, a)
    return {"gagnant": g["ticker"], "regle": 2,
            "raison": (f"à verdict égal, le portefeuille baisse moins dans le pire moment observé : "
                       f"{pct(g['_pire'])} contre {pct(p['_pire'])}")}


# --------------------------------------------------------------------------- le débat du duel
# Deux avocats s'affrontent : chacun défend son titre et attaque l'autre, en citant seulement
# les chiffres des deux dossiers. Le greffier contrôle chaque chiffre cité. Le juge tranche
# ensuite selon la règle fixe ci-dessus : le débat éclaire la décision, il ne la change pas.

def _faits_cote(c: dict) -> str:
    lignes = [f"- {x['libelle']} : {x['avant']} avant, {x['valeur']} après" for x in c["chiffres"]]
    motifs = "\n".join(f"- {m}" for m in c["motifs"]) or "- aucun motif d'alerte"
    return (f"{c['nomTitre']} ({c['ticker']}), {pct(c['taille'], 0)} du portefeuille. "
            f"Verdict du procès : {c['verdict']}.\nChiffres :\n" + "\n".join(lignes) + f"\nMotifs du juge :\n{motifs}")


ARGUMENTS = [
    # (mesure, plus grand = mieux ?, phrase pour le titre défendu)
    ("pire", True, "dans le pire moment observé, le portefeuille baisse moins : {p} contre {c}"),
    ("vol", False, "le portefeuille bouge moins : volatilité de {p} contre {c}"),
    ("an2022", True, "en 2022, l'année de crise, le portefeuille fait {p} contre {c}"),
    ("croissance", True, "le titre a rapporté en moyenne {p} par an, contre {c}"),
    ("risque", False, "le titre pèse moins dans le risque total : {p} contre {c}"),
]


def _plaidoirie_gabarit(pour: dict, contre: dict, nom: str) -> str:
    mp, mc = pour["_mesures"], contre["_mesures"]
    forces = [phrase.format(p=pct(mp[k]), c=pct(mc[k])) for k, plus_grand, phrase in ARGUMENTS
              if (mp[k] > mc[k]) == plus_grand and abs(mp[k] - mc[k]) > 1e-9]
    if forces:
        corps = "Ses atouts face au dossier adverse : " + " ; ".join(forces[:3]) + "."
    else:
        corps = "Sur les chiffres, mon dossier ne domine pas, mais il reste défendable."
    if contre["motifs"]:
        attaque = f" Le dossier adverse, lui, est jugé « {contre['verdict']} » : {contre['motifs'][0].rstrip('.')}."
    else:
        attaque = f" Le dossier adverse est jugé « {contre['verdict']} »."
    return (f"Pour {nom}, je défends {pct(pour['taille'], 0)} dans {pour['nomTitre']}, jugé « {pour['verdict']} ». "
            f"{corps}{attaque}")


def _plaidoirie_bedrock(pour: dict, contre: dict, nom: str, resume: str) -> str:
    import boto3
    from botocore.config import Config

    from .agents import MODELE_PAR_DEFAUT, REGION_PAR_DEFAUT

    client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION") or REGION_PAR_DEFAUT,
                          config=Config(connect_timeout=5, read_timeout=60, retries={"max_attempts": 3}))
    consigne = (
        f"Tu es l'avocat de {pour['nomTitre']} ({pour['ticker']}) dans un duel devant un tribunal "
        f"financier simulé. L'investisseur fictif est {nom} : {resume}. Ton adversaire défend "
        f"{contre['nomTitre']} ({contre['ticker']}). Plaide en 90 à 130 mots, en français, à la "
        "première personne : pourquoi ton titre convient mieux à ce profil, et la faiblesse principale "
        "du titre adverse. Règles strictes : cite UNIQUEMENT des chiffres présents dans les deux dossiers "
        "ci-dessous, tels qu'écrits ; aucune prévision ; aucun conseil personnalisé ; ne prétends pas "
        "connaître le verdict du duel.\n\n"
        f"TON DOSSIER\n{_faits_cote(pour)}\n\nDOSSIER ADVERSE\n{_faits_cote(contre)}"
    )
    reponse = client.converse(
        modelId=os.environ.get("BEDROCK_MODEL_ID") or MODELE_PAR_DEFAUT,
        system=[{"text": consigne}],
        messages=[{"role": "user", "content": [{"text": "Plaidez."}]}],
        inferenceConfig={"maxTokens": 2000},
    )
    texte = "".join(c.get("text", "") for c in reponse["output"]["message"]["content"]).strip()
    if not texte:
        raise ValueError("plaidoirie vide")
    return texte


def debat(profil: Profil, ca: dict, cb: dict, decision: dict, mode: str) -> tuple[list[dict], str | None]:
    """Les tours de parole du duel. Renvoie (tours, avertissement)."""
    from .greffier import nombres_dans

    avertissement = None
    textes = {}
    if mode == "bedrock":
        try:
            with ThreadPoolExecutor(max_workers=2) as ex:
                fa = ex.submit(_plaidoirie_bedrock, ca, cb, profil.nom, profil.resume)
                fb = ex.submit(_plaidoirie_bedrock, cb, ca, profil.nom, profil.resume)
                textes = {ca["ticker"]: fa.result(), cb["ticker"]: fb.result()}
        except Exception as erreur:  # identifiants absents ou expirés, quota, réseau
            avertissement = (f"Débat Bedrock impossible ({type(erreur).__name__}). "
                             "Les plaidoiries du duel ont été écrites par des gabarits.")
    if not textes:
        textes = {ca["ticker"]: _plaidoirie_gabarit(ca, cb, profil.nom),
                  cb["ticker"]: _plaidoirie_gabarit(cb, ca, profil.nom)}

    # Le greffier vérifie que chaque chiffre cité figure dans l'un des deux dossiers.
    admis = set()
    for c in (ca, cb):
        admis |= nombres_dans(_faits_cote(c))
    admis |= nombres_dans(profil.resume)

    tours = []
    for i, (pour, contre) in enumerate(((ca, cb), (cb, ca))):
        texte = textes[pour["ticker"]]
        tours.append({
            "ordre": i + 1,
            "role": "avocat_a" if i == 0 else "avocat_b",
            "acteur": f"L'avocat de {pour['nomTitre']}",
            "ticker": pour["ticker"],
            "texte": texte,
            "non_verifies": sorted(n for n in nombres_dans(texte) if n not in admis),
        })
    tours.append({
        "ordre": 3,
        "role": "juge",
        "acteur": "Le Juge",
        "ticker": decision["gagnant"],
        "texte": (f"J'ai entendu les deux parties. {decision['titre']} : {decision['raison']}. "
                  "Je tranche selon la règle fixe du duel ; les plaidoiries éclairent la décision, "
                  "elles ne la changent pas. Cette simulation n'est pas un conseil financier."),
        "non_verifies": [],
    })
    return tours, avertissement


def juger_duel(profil: Profil, a: tuple[str, float], b: tuple[str, float], mode: str = "bedrock") -> dict:
    # Les deux procès se tiennent en même temps : avec Bedrock, le duel dure à peu près un procès.
    with ThreadPoolExecutor(max_workers=2) as ex:
        fa = ex.submit(ouvrir_proces, profil, a[0], a[1], mode)
        fb = ex.submit(ouvrir_proces, profil, b[0], b[1], mode)
        pa, pb = fa.result(), fb.result()
    ca, cb = _cote(pa), _cote(pb)
    decision = decider(ca, cb)
    noms = {ca["ticker"]: ca["nomTitre"], cb["ticker"]: cb["nomTitre"]}
    if decision["gagnant"]:
        titre = f"Pour {profil.nom}, {noms[decision['gagnant']]} ({decision['gagnant']}) l'emporte"
    else:
        titre = f"Pour {profil.nom}, égalité"
    tours, avertissement_debat = debat(profil, ca, cb, {**decision, "titre": titre}, mode)
    for c in (ca, cb):
        c.pop("_pire")
        c.pop("_mesures")
    return {
        "debat": tours,
        "avertissementDebat": avertissement_debat,
        "profil": profil.cle,
        "nom": profil.nom,
        "cotes": [ca, cb],
        "decision": {**decision, "titre": titre,
                     "texte": f"{titre} : {decision['raison']}. Règle fixe du duel ; "
                              "ce n'est pas un conseil financier, la décision vous appartient."},
    }
