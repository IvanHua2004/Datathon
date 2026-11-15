"""Le greffier lit la question de l'investisseur et dit si le tribunal peut la juger.

Analyse par règles, déterministe et instantanée : pas d'appel au modèle avant le procès.
Une question est recevable si elle demande de juger UNE décision de portefeuille :
placer une part (5 à 50 %) dans UN des 31 actifs du jeu de données.

Statuts :
  recevable  : titre et part trouvés, le procès peut s'ouvrir;
  choix      : question vague (« la tech », « être plus prudent ») ou plusieurs titres :
               le greffier propose les dossiers possibles, l'investisseur en choisit un;
  incomplet  : il manque la part ou le titre, le greffier le demande;
  refus      : le tribunal ne peut pas juger cette question (motif + reformulation);
  fiche, comparaison, catalogue, selection :
               questions de données (« les stats de NVDA », « NVDA ou l'or ? », « quelles
               compagnies ? ») : c'est l'archiviste (rdc/archiviste.py), un autre agent, qui
               répond avec les données seulement, sans juger.

Les thèmes connus sont traduits par règles. Pour une question vague qu'aucune règle ne
reconnaît, le greffier peut demander à Bedrock de proposer des titres, mais seulement parmi
les 31 actifs (RDC_GREFFIER_MODELE=0 pour désactiver, par exemple dans les tests).
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import asdict, dataclass, field

PART_MIN, PART_MAX = 0.02, 0.50

# Noms courants de chaque actif (en minuscules, sans accents). Les symboles courts et
# ambigus (RY, TD, PG, CN) ne sont reconnus qu'en MAJUSCULES dans le texte d'origine.
ALIAS: dict[str, tuple[str, ...]] = {
    "RY.TO": ("banque royale", "royal bank", "rbc"),
    "TD.TO": ("toronto-dominion", "toronto dominion", "banque td"),
    "MFC.TO": ("manulife", "mfc"),
    "ENB.TO": ("enbridge", "enb"),
    "CNQ.TO": ("canadian natural", "cnq"),
    "CNR.TO": ("canadien national", "canadian national", "cnr"),
    "FTS.TO": ("fortis", "fts"),
    "ATD.TO": ("couche-tard", "couche tard", "atd"),
    "SHOP.TO": ("shopify", "shop"),
    "CSU.TO": ("constellation software", "constellation", "csu"),
    "AAPL": ("apple", "aapl"),
    "MSFT": ("microsoft", "msft"),
    "NVDA": ("nvidia", "nvda"),
    "GOOGL": ("alphabet", "google", "googl", "goog"),
    "AMZN": ("amazon", "amzn"),
    "TSLA": ("tesla", "tsla"),
    "JPM": ("jpmorgan", "jp morgan", "jpm"),
    "JNJ": ("johnson & johnson", "johnson and johnson", "johnson", "jnj"),
    "PG": ("procter & gamble", "procter and gamble", "procter", "p&g"),
    "XOM": ("exxon", "exxonmobil", "xom"),
    "XIU.TO": ("tsx 60", "tsx60", "xiu"),
    "SPY": ("s&p 500", "s&p500", "sp500", "spy"),
    "QQQ": ("nasdaq", "nasdaq-100", "qqq"),
    "ESGV": ("esgv", "fnb esg", "etf esg"),
    "XBB.TO": ("obligations canadiennes", "xbb"),
    "ZST.TO": ("ultra court terme", "zst"),
    "AGG": ("obligations americaines", "agg"),
    "TLT": ("bons du tresor", "tresor americain", "tlt"),
    "GLD": ("l'or", "de l'or", "dans l'or", "gold", "gld"),
    "BTC-USD": ("bitcoin", "btc"),
    "ETH-USD": ("ethereum", "ether", "eth"),
}
SYMBOLES_MAJUSCULES = {"RY": "RY.TO", "TD": "TD.TO", "PG": "PG", "CN": "CNR.TO"}

# Titres souvent demandés mais absents des données, avec un remplaçant proche de l'univers.
HORS_UNIVERS: dict[str, tuple[str, ...]] = {
    "coca-cola": ("PG", "JNJ"), "coca cola": ("PG", "JNJ"), "pepsi": ("PG", "ATD.TO"),
    "walmart": ("ATD.TO", "PG"), "costco": ("ATD.TO", "PG"), "mcdonald": ("PG", "ATD.TO"),
    "meta": ("GOOGL", "QQQ"), "facebook": ("GOOGL", "QQQ"), "netflix": ("GOOGL", "QQQ"),
    "amd": ("NVDA", "QQQ"), "intel": ("NVDA", "MSFT"), "disney": ("GOOGL", "SPY"),
    "berkshire": ("SPY", "JPM"), "visa": ("JPM", "RY.TO"), "mastercard": ("JPM", "RY.TO"),
    "bce": ("FTS.TO", "XIU.TO"), "telus": ("FTS.TO", "XIU.TO"), "rogers": ("FTS.TO", "XIU.TO"),
    "bmo": ("RY.TO", "TD.TO"), "scotia": ("RY.TO", "TD.TO"), "cibc": ("RY.TO", "TD.TO"),
    "solana": ("ETH-USD", "BTC-USD"), "dogecoin": ("BTC-USD", "ETH-USD"),
    "ripple": ("BTC-USD", "ETH-USD"), "xrp": ("BTC-USD", "ETH-USD"),
}

MOTS_FINANCE = (
    "portefeuille", "placer", "investir", "investis", "ajouter", "acheter", "action", "titre",
    "fnb", "etf", "obligation", "crypto", "bourse", "allocation", "risque", "diversif",
    "rendement", "placement", "position", "epargne", "argent", "capital", "%",
)
PREDICTION = (
    r"\bva(?:-t-(?:il|elle))? (?:monter|baisser|grimper|chuter|exploser|remonter)",
    r"\bvont (?:monter|baisser)", r"\bmontera\b", r"\bbaissera\b", r"\bvaudra\b",
    r"\bpredi", r"\bprevision", r"\bprevoi", r"\bcombien (?:vaut|vaudra|coutera)",
    r"\bprix (?:de|du|d')\b.*\b(?:demain|dans|en 20\d\d|l'an prochain)",
    r"\battei(?:ndre|ndra)\b", r"\bdemain\b.*\b(?:cours|prix)", r"\bcours\b.*\bdemain\b",
)
ORDRE_REEL = (
    r"^\s*(?:achete|achetez|vends|vendez|vend|place|placez|investis|investissez|passe|passez)\b",
    r"\b(?:achete|achetez|vends|vendez)\b.*\bpour moi\b", r"\bpasse(?:r|z)? (?:un |l')?ordre", r"\bexecute", r"\bmon courtier\b",
    r"\bmon compte (?:reel|de courtage)", r"\bdisnat\b", r"\bwealthsimple\b", r"\bquestrade\b",
)
PART_RE = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*(?:%|pour ?cent|pourcents?|p\.?\s?c\.?)")


# Thèmes vagues -> dossiers possibles : (motifs dans le texte normalisé, [(titre, raison)]).
THEMES: list[tuple[str, tuple[str, ...], list[tuple[str, str]]]] = [
    ("l'intelligence artificielle", (r"\bia\b", r"intelligence artificielle", r"(?<!j')\bai\b"), [
        ("NVDA", "Les puces qui font tourner l'IA"),
        ("MSFT", "L'IA dans les logiciels d'entreprise"),
        ("GOOGL", "La recherche et les modèles d'IA"),
        ("QQQ", "Un panier de 100 grandes technos, plus diversifié"),
    ]),
    ("la technologie", (r"\btech", r"technolog", r"\btechno"), [
        ("QQQ", "Un panier de 100 grandes technos, le plus diversifié"),
        ("NVDA", "Une seule entreprise, très forte croissance"),
        ("MSFT", "Une seule entreprise, établie et rentable"),
        ("AAPL", "Une seule entreprise, établie et rentable"),
        ("SHOP.TO", "La tech canadienne"),
    ]),
    ("la crypto", (r"crypto", r"\bbitcoin", r"\bblockchain"), [
        ("BTC-USD", "La plus ancienne et la plus échangée"),
        ("ETH-USD", "La deuxième, plus volatile"),
    ]),
    ("l'or", (r"\bl'or\b", r"\bde l'or\b", r"\bgold\b", r"metaux precieux", r"valeur refuge",
                  r"(?:\bou|\bet|\bvs|\bversus|\bcontre|\ben) (?:l')?or\b", r"^l?'?or\b"), [
        ("GLD", "Le prix de l'or, souvent stable quand les actions chutent"),
    ]),
    ("les obligations", (r"\bob+lig", r"\bbonds?\b", r"revenu fixe", r"\bfnb d'obligations"), [
        ("XBB.TO", "Obligations canadiennes, toutes échéances"),
        ("ZST.TO", "Obligations à très court terme, le plus stable"),
        ("AGG", "Obligations américaines, toutes échéances"),
        ("TLT", "Obligations du Trésor américain à long terme, plus sensibles aux taux"),
    ]),
    ("plus de prudence", (r"prudent", r"securi", r"moins (?:de )?risqu", r"\bstable", r"proteger mon capital",
                          r"\bfixe\b", r"preserver"), [
        ("XBB.TO", "Obligations canadiennes, toutes échéances"),
        ("ZST.TO", "Obligations à très court terme, le plus stable"),
        ("AGG", "Obligations américaines, toutes échéances"),
        ("TLT", "Obligations du Trésor américain à long terme, plus sensibles aux taux"),
    ]),
    ("les dividendes", (r"dividende", r"\brevenus?\b", r"\brente\b"), [
        ("FTS.TO", "Services publics, dividende régulier"),
        ("ENB.TO", "Pipelines, dividende élevé"),
        ("RY.TO", "Grande banque canadienne"),
        ("JNJ", "Santé, dividende versé depuis des décennies"),
        ("PG", "Biens de consommation courante"),
    ]),
    ("les banques", (r"\bbanque", r"\bbancaire", r"\bfinanciere?s?\b", r"assurance"), [
        ("RY.TO", "Première banque canadienne"),
        ("TD.TO", "Banque canadienne très présente aux États-Unis"),
        ("JPM", "Première banque américaine"),
        ("MFC.TO", "Assurance vie"),
    ]),
    ("l'énergie", (r"energie", r"petrole", r"\bgaz\b", r"pipeline"), [
        ("ENB.TO", "Pipelines canadiens"),
        ("CNQ.TO", "Pétrole canadien"),
        ("XOM", "Pétrole américain"),
    ]),
    ("la santé", (r"\bsante\b", r"pharma", r"medica"), [
        ("JNJ", "Pharmacie et matériel médical"),
    ]),
    ("l'investissement responsable", (r"\besg\b", r"responsable", r"durable", r"ethique", r"\bvert", r"ecolog"), [
        ("ESGV", "Actions américaines filtrées selon des critères ESG"),
        ("FTS.TO", "Services publics canadiens"),
    ]),
    ("le marché canadien", (r"canad", r"\btsx\b", r"quebec"), [
        ("XIU.TO", "Les 60 plus grandes entreprises canadiennes"),
        ("RY.TO", "Première banque canadienne"),
        ("CNR.TO", "Chemin de fer canadien"),
    ]),
    ("les actions américaines", (r"actions? americ", r"bourse americ"), [
        ("SPY", "Les 500 plus grandes entreprises américaines"),
        ("QQQ", "Les 100 plus grandes technos américaines"),
        ("AAPL", "Apple"), ("MSFT", "Microsoft"), ("NVDA", "NVIDIA"), ("JPM", "JPMorgan Chase"),
    ]),
    ("le marché américain", (r"americ", r"etats-unis", r"\busa?\b", r"wall street"), [
        ("SPY", "Les 500 plus grandes entreprises américaines"),
        ("QQQ", "Les 100 plus grandes technos américaines"),
        ("ESGV", "Actions américaines filtrées ESG"),
    ]),
    ("la diversification", (r"diversif", r"\bindice", r"\bfnb\b", r"\betf\b", r"tout le marche", r"passif"), [
        ("SPY", "Les 500 plus grandes entreprises américaines"),
        ("XIU.TO", "Les 60 plus grandes entreprises canadiennes"),
        ("ESGV", "Actions américaines filtrées ESG"),
    ]),
    ("la consommation", (r"consommation", r"commerce", r"magasin", r"epicerie"), [
        ("PG", "Produits du quotidien"),
        ("ATD.TO", "Dépanneurs Couche-Tard"),
        ("AMZN", "Commerce en ligne"),
    ]),
    ("les voitures électriques", (r"voiture", r"electrique", r"automobile"), [
        ("TSLA", "Voitures électriques"),
    ]),
]


def part_par_defaut(ticker: str) -> float:
    """Part proposée quand l'investisseur n'en donne pas : plus petite pour les actifs très volatils."""
    return 0.05 if ticker in ("BTC-USD", "ETH-USD", "GLD") else 0.10


@dataclass
class Choix:
    ticker: str
    nomTitre: str
    taille: float
    question: str
    raison: str


@dataclass
class Analyse:
    statut: str                         # recevable | incomplet | refus
    motif: str                          # ok, part_manquante, titre_manquant, hors_univers, prediction,
                                        # ordre_reel, plusieurs_titres, part_invalide, hors_sujet
    message: str                        # la réponse du greffier, en une ou deux phrases
    ticker: str | None = None
    nom_titre: str | None = None
    taille: float | None = None
    question: str | None = None         # la question telle qu'elle sera inscrite au rôle
    reformulations: list[str] = field(default_factory=list)
    choix: list[Choix] = field(default_factory=list)
    theme: str | None = None
    profil: dict | None = None          # dossier de l'investisseur (statut « profil »)
    definition: dict | None = None      # terme du glossaire (statut « definition »)
    agent: str = "greffier"             # qui répond : le greffier, ou l'archiviste pour les chiffres
    fiches: list[dict] = field(default_factory=list)
    groupes: list[dict] = field(default_factory=list)   # catalogue ou titres à choisir
    selection: str | None = None        # « deux » ou « un_par_groupe » quand il faut choisir
    extraits: list[dict] = field(default_factory=list)  # pièces de l'audience citées par l'archiviste

    def en_json(self) -> dict:
        d = asdict(self)
        d["nomTitre"] = d.pop("nom_titre")
        return d


def _normaliser(texte: str) -> str:
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sans_accents.lower().replace("’", "'")).strip()


def _contient(texte_norm: str, alias: str) -> bool:
    return re.search(rf"(?<![\w&]){re.escape(alias)}(?![\w&])", texte_norm) is not None


def trouver_titres(texte: str, univers: dict[str, str]) -> list[str]:
    """Titres de l'univers nommés dans le texte, dans l'ordre d'apparition."""
    norm = _normaliser(texte)
    trouves: dict[str, int] = {}
    for ticker in univers:
        base = ticker.lower()
        candidats = [base, base.split(".")[0] if "." in base else base, *ALIAS.get(ticker, ())]
        for alias in candidats:
            if len(alias) <= 2:
                continue
            m = re.search(rf"(?<![\w&]){re.escape(alias)}(?![\w&])", norm)
            if m:
                trouves[ticker] = min(trouves.get(ticker, 10**6), m.start())
    for symbole, ticker in SYMBOLES_MAJUSCULES.items():
        m = re.search(rf"(?<![\w.]){symbole}(?![\w])", texte)
        if m and ticker in univers:
            trouves.setdefault(ticker, m.start())
    return sorted(trouves, key=trouves.get)


def trouver_part(texte: str) -> float | None:
    m = PART_RE.search(_normaliser(texte))
    if not m:
        return None
    return float(m.group(1).replace(",", ".")) / 100


def _libelle(ticker: str, univers: dict[str, str]) -> str:
    return f"{univers[ticker]} ({ticker})"


def formuler(ticker: str, taille: float, univers: dict[str, str]) -> str:
    return f"Devrais-je placer {round(taille * 100):g} % de mon portefeuille dans {_libelle(ticker, univers)} ?"


def _proposer(candidats: list[tuple[str, str]], part: float | None, univers: dict[str, str]) -> list[Choix]:
    resultat = []
    for ticker, raison in candidats:
        if ticker not in univers:
            continue
        taille = part if part is not None else part_par_defaut(ticker)
        resultat.append(Choix(ticker, univers[ticker], taille, formuler(ticker, taille, univers), raison))
    return resultat


def theme_reconnu(texte_norm: str) -> tuple[str, list[tuple[str, str]]] | None:
    for nom, motifs, candidats in THEMES:
        if any(re.search(m, texte_norm) for m in motifs):
            return nom, candidats
    return None


def themes_reconnus(texte_norm: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """Thèmes nommés dans le texte. Un thème plus précis cache un thème plus large qui
    reconnaît les mêmes mots (« actions américaines » cache « marché américain »)."""
    trouves, positions = [], []
    for nom, motifs, candidats in THEMES:
        spans = [m.span() for p in motifs for m in [re.search(p, texte_norm)] if m]
        if spans and not any(a <= s0 < b for s0, _ in spans for a, b in positions):
            trouves.append((nom, candidats))
            positions += spans
    return trouves


def titres_du_theme(nom: str) -> list[str]:
    for n, _, candidats in THEMES:
        if n == nom:
            return [t for t, _ in candidats]
    return []


def _parts_proposees(ticker: str, univers: dict[str, str]) -> list[Choix]:
    parts = (0.02, 0.05, 0.10) if part_par_defaut(ticker) < 0.10 else (0.05, 0.10, 0.20)
    return [Choix(ticker, univers[ticker], x, formuler(ticker, x, univers), libelle)
            for x, libelle in zip(parts, ("Une petite part", "Une part moyenne", "Une part importante"))]


def _archiviste(norm: str, titres: list[str], univers: dict[str, str],
                portefeuille: set[str], classes_exclues: set[str]) -> Analyse | None:
    """Routage vers l'archiviste. Renvoie None si la question n'est pas pour lui."""
    from . import archiviste

    themes = [(nom, [t for t, _ in cands if t in univers]) for nom, cands in themes_reconnus(norm)]
    themes = [(nom, ts) for nom, ts in themes if ts and not any(t in titres for t in ts)]
    nb_groupes = len(titres) + len(themes)
    veut_chiffres = archiviste.demande_des_chiffres(norm)
    veut_comparer = archiviste.demande_une_comparaison(norm)

    def titre(t: str) -> dict:
        return archiviste._titre(t, portefeuille, classes_exclues)

    # 1. La liste des actifs (tous, ou ceux d'un domaine).
    if not titres and archiviste.demande_le_catalogue(norm):
        if len(themes) == 1:
            r = archiviste.catalogue(portefeuille, classes_exclues, seulement=themes[0][1], theme=themes[0][0])
        else:
            r = archiviste.catalogue(portefeuille, classes_exclues)
        return Analyse("catalogue", "catalogue", r["message"], agent="archiviste", groupes=r["groupes"])

    comparaison_explicite = re.search(r"compar|\bvs\.?\b|\bversus\b|\bcontre\b|difference", norm)
    veut_moyenne = re.search(r"\bmoyenn", norm)

    # 2a. « La moyenne des obligations vs les actions américaines » : paniers à parts égales.
    if nb_groupes == 2 and veut_moyenne and themes:
        cotes = titres + [archiviste.PREFIXE_MOYENNE + nom if len(ts) > 1 else ts[0] for nom, ts in themes]
        r = archiviste.comparer(*cotes)
        return Analyse("comparaison", "comparaison", r["message"], agent="archiviste", fiches=r["fiches"],
                       choix=[Choix(t, univers[t], part_par_defaut(t), formuler(t, part_par_defaut(t), univers),
                                    "Soumettre ce titre au tribunal") for t in cotes if t in univers])

    # 2b. Une comparaison dont un seul côté est reconnu : on demande l'autre.
    if nb_groupes == 1 and comparaison_explicite:
        connu = univers[titres[0]] if titres else themes[0][0]
        return Analyse("incomplet", "comparaison_incomplete",
                       f"J'ai reconnu « {connu} », mais pas l'autre côté de la comparaison. Avec quoi "
                       "voulez-vous le comparer ? Un titre (NVDA, SPY…) ou un domaine (obligations, or, "
                       "crypto, tech…).", agent="archiviste")

    # 2c. Une comparaison : exactement deux titres, sinon on fait préciser.
    if nb_groupes >= 2 and (veut_comparer or veut_chiffres):
        uniques = titres + [ts[0] for _, ts in themes if len(ts) == 1]
        if nb_groupes == 2 and len(uniques) == 2:
            a, b = uniques
            r = archiviste.comparer(a, b)
            choix = [Choix(t, univers[t], part_par_defaut(t), formuler(t, part_par_defaut(t), univers),
                           "Soumettre ce titre au tribunal") for t in (a, b) if t in univers]
            return Analyse("comparaison", "comparaison", r["message"], agent="archiviste",
                           fiches=r["fiches"], choix=choix)
        groupes = ([{"nom": univers[t], "titres": [titre(t)]} for t in titres]
                   + [{"nom": nom.capitalize(),
                       "titres": ([archiviste.option_moyenne(nom, len(ts))] if len(ts) > 1 else [])
                                 + [titre(t) for t in ts]}
                      for nom, ts in themes])
        if len(groupes) == 2:
            r = archiviste.selection(groupes, un_par_groupe=True)
        else:
            if not themes:
                groupes = [{"nom": "Titres nommés", "titres": [titre(t) for t in titres]}]
            r = archiviste.selection(groupes, un_par_groupe=False)
        return Analyse("selection", "selection", r["message"], agent="archiviste",
                       groupes=r["groupes"], selection=r["selection"])

    # 3. Les chiffres d'un seul titre.
    if len(titres) == 1 and not themes and veut_chiffres:
        t = titres[0]
        r = archiviste.repondre(t)
        return Analyse("fiche", "chiffres", r["message"], ticker=t, nom_titre=univers[t],
                       choix=_parts_proposees(t, univers), agent="archiviste", fiches=r["fiches"])
    return None


def _message_choix(theme: str | None, choix: list[Choix]) -> str:
    if len(choix) == 1:
        c = choix[0]
        return (f"Pour {theme}, le tribunal dispose d'un seul dossier : {c.nomTitre} ({c.ticker}). "
                "Cliquez pour ouvrir le débat, ou précisez la part.")
    sujet = f"Pour {theme}, voici" if theme else "Voici"
    return (f"{sujet} les dossiers que le tribunal peut juger. Choisissez-en un pour ouvrir "
            "le débat, ou précisez votre question.")


def interpreter_avec_modele(texte: str, univers: dict[str, str], resume_profil: str) -> list[tuple[str, str]]:
    """Demande à Bedrock 1 à 4 titres de l'univers qui traduisent une question vague.

    Le modèle ne peut choisir que dans la liste fournie : tout autre titre est écarté.
    Renvoie [] si Bedrock est désactivé, indisponible ou si la réponse est inutilisable.
    """
    if os.environ.get("RDC_GREFFIER_MODELE", "1") == "0":
        return []
    try:
        import boto3
        from botocore.config import Config

        from .agents import MODELE_PAR_DEFAUT, REGION_PAR_DEFAUT

        client = boto3.client(
            "bedrock-runtime",
            region_name=os.environ.get("AWS_REGION") or REGION_PAR_DEFAUT,
            config=Config(connect_timeout=5, read_timeout=25, retries={"max_attempts": 2}),
        )
        liste = "\n".join(f"- {t} : {n}" for t, n in univers.items())
        consigne = (
            "Tu es le greffier d'un tribunal financier simulé. Un investisseur fictif pose une "
            "question vague. Propose de 1 à 4 titres, choisis UNIQUEMENT dans la liste, qui "
            "permettraient de juger sa question. Si la question ne porte pas sur un placement, "
            "renvoie une liste vide. Réponds seulement en JSON : "
            '{"choix": [{"ticker": "...", "raison": "moins de 12 mots, en français"}]}\n\n'
            f"Profil : {resume_profil}\nTitres disponibles :\n{liste}"
        )
        reponse = client.converse(
            modelId=os.environ.get("BEDROCK_MODEL_ID") or MODELE_PAR_DEFAUT,
            system=[{"text": consigne}],
            messages=[{"role": "user", "content": [{"text": texte[:500]}]}],
            inferenceConfig={"maxTokens": 2000},
        )
        bloc = "".join(c.get("text", "") for c in reponse["output"]["message"]["content"])
        donnees = json.loads(bloc[bloc.index("{"): bloc.rindex("}") + 1])
        return [(c["ticker"], str(c.get("raison", ""))[:120])
                for c in donnees.get("choix", []) if c.get("ticker") in univers][:4]
    except Exception:
        return []


# --------------------------------------------------------------------------- mémoire de la conversation
# Une relance courte (« et Microsoft ? », « plutôt 15 % », « compare-le avec l'or », « ses stats »)
# se lit avec les questions précédentes. La plus récente a priorité : on remonte l'historique
# du dernier message vers le premier et on prend la première information trouvée.
RELANCE = (
    r"^(?:et|ou|plutot|sinon|alors|avec|pareil|meme chose|idem|aussi|maintenant|ok|d'accord)\b",
    r"\b(?:le|la|les|ce|cet|cette|celui|celle|ca|cela|lui|il|elle|son|sa|ses|leur|leurs)\b"
    r"(?:-(?:ci|la))?\s*(?:\?|$|titre|actif|action|dernier|meme|stats?|chiffres|performance)",
    r"-(?:le|la|les|lui)\b", r"\bmeme titre\b", r"\bcelui-(?:ci|la)\b",
)


@dataclass
class Contexte:
    titres: list[str]          # titres nommés, du plus récent au plus ancien
    part: float | None         # dernière part citée
    theme: str | None          # dernier domaine cité


def lire_contexte(historique: list[str], univers: dict[str, str]) -> Contexte:
    titres: list[str] = []
    part = None
    theme = None
    for message in reversed(historique[-10:]):
        for t in trouver_titres(message, univers):
            if t not in titres:
                titres.append(t)
        if part is None:
            x = trouver_part(message)
            part = x if x is not None and PART_MIN <= x <= PART_MAX else None
        if theme is None:
            th = theme_reconnu(_normaliser(message))
            theme = th[0] if th else None
    return Contexte(titres, part, theme)


def est_une_relance(texte_norm: str) -> bool:
    return len(texte_norm.split()) <= 6 or any(re.search(m, texte_norm) for m in RELANCE)


def _reponse_profil(norm: str, p: dict) -> str:
    """Une phrase qui répond à la question précise, puis le dossier complet."""
    nom = p["nom"]
    reponses = []
    if re.search(r"budget|perte|tolerance|limite", norm):
        reponses.append(f"Le budget de perte déclaré de {nom} est de {round(p['budgetPerte'] * 100):g} % du portefeuille.")
    if re.search(r"horizon|quand|combien de temps", norm):
        reponses.append(f"Son horizon est d'environ {p['horizonAns']:g} ans.")
    if re.search(r"capital|combien j'?ai|argent", norm):
        reponses.append(f"Son capital (fictif) est de {p['capital']:,.0f} $.".replace(",", " "))
    if re.search(r"objectif|but", norm):
        reponses.append(f"Son objectif : {p['objectif'].rstrip('.').lower()}.")
    if re.search(r"plafond|maximum|max", norm):
        reponses.append(f"Un seul titre ne doit pas dépasser {round(p['plafondPosition'] * 100):g} % du portefeuille.")
    if re.search(r"crypto|exclu|interdit|pas avoir|peux pas", norm):
        if p.get("classesExclues"):
            reponses.append(f"{nom} exclut ces classes d'actifs : {', '.join(p['classesExclues'])}. "
                            "Un placement dans l'une d'elles sera jugé contraire à son profil.")
        else:
            reponses.append(f"{nom} n'exclut aucune classe d'actifs.")
    debut = " ".join(reponses) + " " if reponses else ""
    if not p.get("portefeuilleDeclare", True):
        return (f"{debut}Voici le dossier de {nom}, tel qu'il a été déclaré (profil fictif). "
                "Sa note ne décrit pas ses positions : le tribunal raisonne donc sur un portefeuille "
                "de référence fictif, pas sur le sien. Pour le préciser, ajoutez-les dans la note "
                "du persona (par exemple « SPY 60 %, XBB.TO 40 % »).")
    return f"{debut}Voici le dossier de {nom}, tel qu'il a été déclaré (profil fictif)."


_VOTRE_PORTEFEUILLE = [
    (re.compile(r"\b([Dd])e (?:votre|mon) portefeuille\b"), r"\1u portefeuille de référence"),
    (re.compile(r"\b(?:votre|mon) portefeuille\b"), "le portefeuille de référence"),
    (re.compile(r"\b(?:Votre|Mon) portefeuille\b"), "Le portefeuille de référence"),
]


def sans_votre_portefeuille(texte: str) -> str:
    """Pour un persona dont on ne connaît pas les positions : jamais « votre portefeuille »."""
    for motif, remplacement in _VOTRE_PORTEFEUILLE:
        texte = motif.sub(remplacement, texte)
    return texte


def adapter_au_portefeuille_de_reference(a: "Analyse") -> "Analyse":
    a.message = sans_votre_portefeuille(a.message)
    if a.question:
        a.question = sans_votre_portefeuille(a.question)
    a.reformulations = [sans_votre_portefeuille(r) for r in a.reformulations]
    for c in a.choix:
        c.question = sans_votre_portefeuille(c.question)
    return a


def analyser(texte: str, univers: dict[str, str], ticker_en_attente: str | None = None,
             taille_en_attente: float | None = None, titre_exemple: str = "SPY",
             resume_profil: str = "", portefeuille: set[str] = frozenset(),
             classes_exclues: set[str] = frozenset(), historique: list[str] | None = None,
             profil_info: dict | None = None, _profondeur: int = 0) -> Analyse:
    """Analyse une réponse au greffier, en tenant compte des questions précédentes.

    univers : ticker -> nom. ticker_en_attente / taille_en_attente : ce que le greffier
    sait déjà d'un échange précédent (« Et pour 20 % ? » après avoir nommé le titre).
    """
    norm = _normaliser(texte)
    if not norm:
        return Analyse("incomplet", "vide", "Je vous écoute : nommez un titre et la part de votre portefeuille.")

    from . import conversation

    titres = trouver_titres(texte, univers)
    part = trouver_part(texte)
    rappel = None   # ce que le greffier a repris de la conversation, dit à l'investisseur
    nom = profil_info["nom"] if profil_info else "l'investisseur"

    # Politesse : bonjour, merci, recommencer.
    poli = conversation.politesse(norm, nom)
    if poli and not titres:
        return Analyse("social", poli[0], poli[1])

    # Le dossier de l'investisseur : c'est l'archiviste qui le lit, sans juger.
    if (profil_info and conversation.question_sur_le_profil(norm) and part is None and not titres
            and not re.search(r"\b(?:placer|investir|acheter|ajouter|mettre|vendre)\b", norm)):
        return Analyse("profil", "profil", _reponse_profil(norm, profil_info), agent="archiviste",
                       profil=profil_info)

    # Les mots du tribunal : définition écrite à la main, avec l'exemple du persona si utile.
    terme = conversation.terme_demande(norm, bool(titres))
    if terme:
        texte_def = conversation.GLOSSAIRE[terme][1]
        exemple = conversation.exemple_pour(terme, profil_info)
        return Analyse("definition", "definition", texte_def, agent="archiviste",
                       definition={"terme": terme, "texte": texte_def, "exemple": exemple})

    # Fautes de frappe : « nvidai » -> NVIDIA, dit à l'investisseur.
    approximations = []
    if not titres and not themes_reconnus(norm):
        approximations = conversation.titres_approchants(norm, univers, ALIAS)
        titres = [t for _, t in approximations]

    contexte = lire_contexte(historique or [], univers)
    autres_themes = [nom for nom, cands in themes_reconnus(norm) if not any(t in titres for t, _ in cands)]
    if historique and est_une_relance(norm) and not autres_themes:
        from . import archiviste
        demande_donnees = archiviste.demande_des_chiffres(norm) or archiviste.demande_une_comparaison(norm)
        if not titres and contexte.titres and (part is not None or demande_donnees
                                              or any(re.search(m, norm) for m in RELANCE)):
            # « plutôt 15 % », « ses stats ? » : le titre vient du message le plus récent qui en nomme un.
            if not (ticker_en_attente and part is not None):
                titres = [contexte.titres[0]]
                rappel = f"D'après la conversation, il s'agit de {univers[titres[0]]} ({titres[0]})."
        elif len(titres) == 1 and re.search(r"compar|\bvs\b|\bversus\b|\bcontre\b|\bavec\b", norm):
            # « compare avec l'or » : l'autre côté est le titre le plus récent de la conversation.
            autre = next((t for t in contexte.titres if t != titres[0]), None)
            if autre:
                titres = [autre, titres[0]]
                rappel = f"D'après la conversation, je compare avec {univers[autre]} ({autre})."
        if len(titres) == 1 and part is None and contexte.part is not None and not demande_donnees:
            # « et Microsoft ? » après « 10 % dans Apple ? » : on garde la part la plus récente.
            part = contexte.part
            rappel = (rappel + " " if rappel else "") + f"Je garde la part de {round(part * 100):g} %."

    if approximations:
        compris = ", ".join(f"« {mot} » comme {univers[t]} ({t})" for mot, t in approximations)
        rappel = f"J'ai compris {compris}." + (f" {rappel}" if rappel else "")

    analyse = _analyser(texte, norm, titres, part, univers, ticker_en_attente, taille_en_attente,
                        titre_exemple, resume_profil, portefeuille, classes_exclues)

    # Dernier recours : les règles n'ont pas compris, Bedrock classe la question et la réécrit.
    if _profondeur == 0 and analyse.motif in ("hors_sujet", "titre_manquant"):
        classement = conversation.classer_avec_modele(texte, univers, resume_profil, historique or [])
        if classement and classement["intention"] == "decision" and len(classement["tickers"]) > 1:
            choix = _proposer([(t, "Proposé d'après votre question") for t in classement["tickers"]],
                              classement["part"], univers)
            return Analyse("choix", "interpretation", _message_choix(None, choix), choix=choix)
        canon = conversation.question_canonique(classement) if classement else None
        if canon:
            relue = analyser(canon, univers, ticker_en_attente, taille_en_attente, titre_exemple,
                             resume_profil, portefeuille, classes_exclues, historique, profil_info,
                             _profondeur=1)
            relue.message = f"J'ai compris : « {canon} ». {relue.message}"
            return relue

    if rappel:
        analyse.message = f"{rappel} {analyse.message}"
    return analyse


def _analyser(texte: str, norm: str, titres: list[str], part: float | None, univers: dict[str, str],
              ticker_en_attente: str | None, taille_en_attente: float | None, titre_exemple: str,
              resume_profil: str, portefeuille: set[str], classes_exclues: set[str]) -> Analyse:
    exemple = titres[0] if titres else (ticker_en_attente or titre_exemple)
    exemple_part = part if part and PART_MIN <= part <= PART_MAX else (taille_en_attente or 0.10)

    if any(re.search(p, norm) for p in ORDRE_REEL):
        return Analyse(
            "refus", "ordre_reel",
            "Le tribunal ne passe aucun ordre : rien n'est acheté ni vendu ici. "
            "Il peut en revanche juger cette décision en simulation.",
            reformulations=[formuler(exemple, exemple_part, univers)],
        )

    if any(re.search(p, norm) for p in PREDICTION):
        return Analyse(
            "refus", "prediction",
            "Le tribunal ne prédit pas les cours. Il juge si une décision convient à votre "
            "profil, à partir de l'historique des prix.",
            reformulations=[formuler(exemple, exemple_part, univers)],
        )

    # Questions de données (liste des actifs, chiffres, comparaison), sans décision à juger :
    # c'est l'archiviste qui répond, pas le greffier.
    from . import archiviste as _arch
    demande_explicite = (_arch.demande_des_chiffres(norm) or _arch.demande_le_catalogue(norm)
                         or re.search(r"compar|\bvs\.?\b|\bversus\b|\bcontre\b|difference", norm))
    if part is None and (not ticker_en_attente or demande_explicite):
        reponse = _archiviste(norm, titres, univers, portefeuille, classes_exclues)
        if reponse is not None:
            return reponse

    if not titres:
        for nom, proches in HORS_UNIVERS.items():
            if _contient(norm, nom):
                return Analyse(
                    "refus", "hors_univers",
                    f"Le tribunal n'a pas de données sur {nom.title()}. Il juge seulement les "
                    "31 actifs du jeu de données. Voici des titres proches :",
                    reformulations=[formuler(t, exemple_part, univers) for t in proches if t in univers],
                )
        theme = None if ticker_en_attente else theme_reconnu(norm)
        part_valide = part if part is not None and PART_MIN <= part <= PART_MAX else None
        if theme:
            nom, candidats = theme
            choix = _proposer(candidats, part_valide, univers)
            return Analyse("choix", "theme", _message_choix(nom, choix), choix=choix, theme=nom)
        if ticker_en_attente:
            titres = [ticker_en_attente]
        elif part is not None or any(m in norm for m in MOTS_FINANCE):
            return Analyse(
                "incomplet", "titre_manquant",
                "Dans quel titre ? Le tribunal connaît 31 actifs : actions canadiennes et "
                "américaines, FNB, obligations, or et cryptoactifs.",
                taille=part if part and PART_MIN <= part <= PART_MAX else None,
            )
        else:
            return Analyse(
                "refus", "hors_sujet",
                "Ce service débat seulement de décisions de portefeuille. "
                "Posez une question sur un titre et une part de votre portefeuille.",
                reformulations=[formuler(titre_exemple, 0.10, univers)],
            )

    if len(titres) > 1:
        part_valide = part if part is not None and PART_MIN <= part <= PART_MAX else None
        choix = _proposer([(t, "Nommé dans votre question") for t in titres[:4]], part_valide, univers)
        return Analyse(
            "choix", "plusieurs_titres",
            ("Vous pouvez soumettre un seul de ces titres au tribunal, ou les opposer dans un débat "
             "pour savoir lequel convient le mieux à votre profil."
             if len(choix) == 2 else
             "Un procès à la fois : le tribunal juge un seul titre par audience. Lequel voulez-vous soumettre ?"),
            choix=choix,
        )

    ticker = titres[0]
    if part is None:
        part = taille_en_attente
    if part is None:
        parts = (0.02, 0.05, 0.10) if part_par_defaut(ticker) < 0.10 else (0.05, 0.10, 0.20)
        choix = [Choix(ticker, univers[ticker], t, formuler(ticker, t, univers),
                       "Une petite part" if i == 0 else "Une part moyenne" if i == 1 else "Une part importante")
                 for i, t in enumerate(parts)]
        return Analyse(
            "choix", "part_manquante",
            f"Bien noté : {_libelle(ticker, univers)}. Quelle part de votre portefeuille voulez-vous "
            "soumettre au tribunal ? Choisissez, ou écrivez la vôtre (jusqu’à 50 %).",
            ticker=ticker, nom_titre=univers[ticker], choix=choix,
        )
    if part < PART_MIN - 1e-9 or part > PART_MAX + 1e-9:
        return Analyse(
            "refus", "part_invalide",
            f"Le tribunal juge des parts de 2 % à 50 % du portefeuille : "
            f"{round(part * 100, 1):g} % est hors de cette fourchette.",
            ticker=ticker, nom_titre=univers[ticker],
            reformulations=[formuler(ticker, t, univers) for t in (0.10, 0.20)],
        )

    question = formuler(ticker, part, univers)
    return Analyse(
        "recevable", "ok",
        f"Recevable. J'inscris au rôle : « placer {round(part * 100):g} % du portefeuille dans "
        f"{_libelle(ticker, univers)} ». La Défense et le Procureur plaideront à partir des données.",
        ticker=ticker, nom_titre=univers[ticker], taille=part, question=question,
    )
