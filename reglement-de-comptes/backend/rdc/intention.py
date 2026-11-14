"""Interprétation en langage naturel des intentions d'investissement.

Permet à l'utilisateur de soumettre une requête libre telle que :
« devrais acheter +30% dans des etf ? » ou « je veux mettre 20% sur NVDA ».
"""
from __future__ import annotations

import re
import os
import json
import pandas as pd

from .profils import Profil

# Mappage de synonymes courants vers les tickers de l'univers de 31 actifs
SYNONYMES_TICKERS: dict[str, str] = {
    # Cryptos
    "bitcoin": "BTC-USD",
    "btc": "BTC-USD",
    "crypto": "BTC-USD",
    "ether": "ETH-USD",
    "ethereum": "ETH-USD",
    "eth": "ETH-USD",

    # Actions Tech
    "nvidia": "NVDA",
    "nvda": "NVDA",
    "ia": "NVDA",
    "ai": "NVDA",
    "apple": "AAPL",
    "aapl": "AAPL",
    "microsoft": "MSFT",
    "msft": "MSFT",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "amazon": "AMZN",
    "amzn": "AMZN",
    "tesla": "TSLA",
    "tsla": "TSLA",
    "shopify": "SHOP.TO",
    "shop": "SHOP.TO",
    "constellation": "CSU.TO",

    # Énergie & Pétrole
    "enbridge": "ENB.TO",
    "enb": "ENB.TO",
    "exxon": "XOM",
    "xom": "XOM",
    "canadian natural": "CNQ.TO",
    "cnq": "CNQ.TO",
    "petrole": "ENB.TO",
    "pétrole": "ENB.TO",
    "energie": "ENB.TO",
    "énergie": "ENB.TO",

    # Banques & Finance
    "royal bank": "RY.TO",
    "rbc": "RY.TO",
    "ry": "RY.TO",
    "td": "TD.TO",
    "jpmorgan": "JPM",
    "jpm": "JPM",
    "manulife": "MFC.TO",
    "mfc": "MFC.TO",
    "banque": "RY.TO",
    "banques": "RY.TO",

    # Consommation & Santé
    "couche-tard": "ATD.TO",
    "couchetard": "ATD.TO",
    "atd": "ATD.TO",
    "johnson": "JNJ",
    "jnj": "JNJ",
    "procter": "PG",
    "pg": "PG",
    "fortis": "FTS.TO",
    "canadien national": "CNR.TO",
    "cnr": "CNR.TO",

    # FNB & Marchés
    "spy": "SPY",
    "s&p": "SPY",
    "s&p 500": "SPY",
    "nasdaq": "QQQ",
    "qqq": "QQQ",
    "tsx": "XIU.TO",
    "xiu": "XIU.TO",
    "esgv": "ESGV",
    "esg": "ESGV",
    "or": "GLD",
    "gold": "GLD",
    "gld": "GLD",
    "obligations": "XBB.TO",
    "bonds": "XBB.TO",
    "xbb": "XBB.TO",
    "zst": "ZST.TO",
    "tlt": "TLT",
    "agg": "AGG",
}


def _extraire_pourcentage(texte: str, defaut: float = 0.20) -> float:
    """Extrait un pourcentage du texte (ex: '30%', '+30 %', '0.25')."""
    # Chercher motif de pourcentage explicite
    m = re.search(r"(?:\+|\b)(\d+(?:[.,]\d+)?)\s*%", texte)
    if m:
        val = float(m.group(1).replace(",", "."))
        return max(0.01, min(1.0, val / 100.0))
    # Chercher décimal direct (ex: 0.20)
    m2 = re.search(r"\b0[.,](\d{1,2})\b", texte)
    if m2:
        val = float("0." + m2.group(1))
        return max(0.01, min(1.0, val))
    return defaut


def _etf_selon_profil(profil: Profil) -> str:
    """Sélectionne le FNB le plus cohérent avec le profil si l'utilisateur demande génériquement 'des ETF'."""
    if profil.cle == "amira":
        return "QQQ"         # FNB orienté croissance / technologique
    elif profil.cle == "mateo":
        return "ESGV"        # FNB américain filtré ESG
    else: # robert
        return "XBB.TO"      # FNB obligataire prudent


def _resoudre_ticker_heuristique(texte: str, univers: pd.DataFrame, profil: Profil) -> tuple[str, str]:
    """Détecte le ticker cible par règles heuristiques robustes."""
    propre = texte.lower().strip()

    # 1. Vérification si un ticker exact est écrit en majuscules ou isolé
    for t in univers.index:
        pattern = r"\b" + re.escape(t.lower().replace(".to", "")) + r"(?:\.to)?\b"
        if re.search(pattern, propre):
            return t, f"Actif identifié : {t} ({univers.loc[t, 'name']})."

    # 2. Vérification par synonymes
    for cle, t in SYNONYMES_TICKERS.items():
        if re.search(r"\b" + re.escape(cle) + r"\b", propre):
            return t, f"Terme « {cle} » associé à l'actif : {t} ({univers.loc[t, 'name']})."

    # 3. Mention générique d'ETF / FNB
    if any(k in propre for k in ["etf", "fnb", "fonds", "tracker"]):
        cible = _etf_selon_profil(profil)
        return cible, f"Demande générique de FNB/ETF résolue vers {cible} ({univers.loc[cible, 'name']}) selon les affinités de {profil.nom}."

    # 4. Fallback sur la demande par défaut du persona
    cible, _ = profil.demande_exemple
    return cible, f"Aucun actif spécifique détecté ; utilisation de l'exemple du profil : {cible} ({univers.loc[cible, 'name']})."


def interpreter_intention(texte: str, univers: pd.DataFrame, profil: Profil,
                          mode: str = "gabarit") -> tuple[str, float, str]:
    """Interprète la volonté libre de l'utilisateur et retourne (ticker, taille, explication).
    
    Exemples d'entrées :
    - « devrais acheter +30% dans des etf ? » -> ('QQQ', 0.30, ...)
    - « placer 10% sur du pétrole Enbridge » -> ('ENB.TO', 0.10, ...)
    - « 20% NVDA » -> ('NVDA', 0.20, ...)
    """
    if not texte or not texte.strip():
        t, taille = profil.demande_exemple
        return t, taille, f"Demande par défaut pour {profil.nom} : {taille*100:.0f} % dans {t}."

    taille = _extraire_pourcentage(texte, defaut=profil.demande_exemple[1])
    ticker, motif = _resoudre_ticker_heuristique(texte, univers, profil)

    explication = f"Intention comprise : allocation de {taille*100:.0f} % dans {ticker}. {motif}"
    return ticker, taille, explication
