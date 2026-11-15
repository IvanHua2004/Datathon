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
        ],
        "_pire": pire,
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
    for c in (ca, cb):
        c.pop("_pire")
    return {
        "profil": profil.cle,
        "nom": profil.nom,
        "cotes": [ca, cb],
        "decision": {**decision, "titre": titre,
                     "texte": f"{titre} : {decision['raison']}. Règle fixe du duel ; "
                              "ce n'est pas un conseil financier, la décision vous appartient."},
    }
