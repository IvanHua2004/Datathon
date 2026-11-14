"""Règlement de comptes : interface Streamlit.

Lancer depuis le dossier du projet : streamlit run frontend/app.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

import graphiques

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from rdc import donnees, temoins
from rdc.format import dollars, pct
from rdc.profils import PROFILS
from rdc.proces import (V_COMPATIBLE, V_CONTRAINTE, V_INDECIDABLE, V_TENSION, courbe,
                        ouvrir_proces)

st.set_page_config(page_title="Règlement de comptes", layout="wide")

ICONES = {V_CONTRAINTE: "⛔", V_TENSION: "⚠️", V_INDECIDABLE: "❔", V_COMPATIBLE: "✅"}

st.title("Règlement de comptes")
st.caption("Avant d'investir, faites passer votre idée en procès. "
           "Simulation pédagogique sur des profils fictifs : ce n'est pas un conseil financier.")

SOURCE_S3 = os.environ.get("RDC_S3_BUCKET")
try:
    d = donnees.charger()
except Exception as erreur:  # fichier absent, identifiants AWS absents ou expirés, bucket introuvable
    if SOURCE_S3:
        st.error(f"Lecture impossible dans S3 (bucket `{SOURCE_S3}`) : {type(erreur).__name__} : {erreur}. "
                 "Collez des identifiants récents depuis « Get AWS CLI credentials » dans Workshop Studio, "
                 "ou retirez RDC_S3_BUCKET pour lire les fichiers locaux.")
    else:
        st.error("Données introuvables. Définissez la variable RDC_DATA_DIR vers le dossier "
                 f"`alphaforge_starter`. Détail : {erreur}")
    st.stop()

with st.sidebar:
    st.header("Le dossier")
    profils = list(PROFILS)
    persona = st.query_params.get("persona")
    index_initial = profils.index(persona) if persona in PROFILS else 0
    cle = st.selectbox("Investisseur (fictif)", profils, index=index_initial,
                       format_func=lambda c: PROFILS[c].nom)
    profil = PROFILS[cle]
    st.write(profil.resume)
    st.write(f"**Objectif :** {profil.objectif}")
    st.write(f"**Préférences :** {profil.preferences}")
    st.write(f"**Capital (hypothèse) :** {dollars(profil.capital)}")
    st.write(f"**Budget de perte (hypothèse) :** {pct(profil.budget_perte, 0)}")

    st.header("La demande")
    titres = list(d.univers.index)
    ticker = st.selectbox("Titre à ajouter", titres, index=titres.index(profil.demande_exemple[0]),
                          format_func=lambda t: f"{t} — {d.univers.loc[t, 'name']}")
    taille = st.select_slider("Part du portefeuille à y placer", options=[0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50],
                              value=profil.demande_exemple[1], format_func=lambda x: pct(x, 0))
    mode = st.radio("Agents", ["gabarit", "bedrock"],
                    format_func=lambda m: {"gabarit": "Sans modèle (gabarits)", "bedrock": "Amazon Bedrock (Strands)"}[m],
                    help="Le mode Bedrock exige des identifiants AWS et un modèle activé.")
    lancer = st.button("Ouvrir le procès", type="primary", width="stretch")
    st.caption("Données : " + (f"Amazon S3, bucket `{SOURCE_S3}`" if SOURCE_S3 else "fichiers locaux")
               + f" · Région AWS : {os.environ.get('AWS_REGION') or 'us-east-1'}")

if lancer:
    with st.spinner("Le tribunal siège..."):
        st.session_state["proces"] = ouvrir_proces(profil, ticker, taille, mode)

proces = st.session_state.get("proces")
if proces is None:
    st.info("Choisissez un investisseur et une demande, puis ouvrez le procès.")
    st.subheader("Portefeuille actuel (fictif)")
    st.dataframe(pd.DataFrame({"Poids": {t: pct(p / sum(profil.portefeuille.values()))
                                         for t, p in profil.portefeuille.items()}}))
    st.stop()

dossier, dec = proces.dossier, proces.decision
if proces.avertissement:
    st.warning(proces.avertissement)

st.subheader(f"{dossier.profil.nom} demande {pct(dossier.taille, 0)} du portefeuille dans {dossier.ticker}")


def afficher(plaidoirie) -> None:
    st.markdown(f"#### {plaidoirie.role}")
    if plaidoirie.temoins_convoques:
        st.caption("Témoins convoqués : " + ", ".join(plaidoirie.temoins_convoques))
    st.write(plaidoirie.texte.replace("$", "\\$"))
    if plaidoirie.non_verifies:
        st.error("Greffier : chiffres absents des pièces → " + ", ".join(plaidoirie.non_verifies))
    else:
        st.caption("Greffier : tous les chiffres cités figurent dans les pièces.")


gauche, milieu, droite = st.columns(3)
with gauche:
    afficher(proces.plaidoiries[0])
with milieu:
    afficher(proces.plaidoiries[1])
with droite:
    st.markdown("#### Le Juge")
    st.markdown(f"### {ICONES[dec['verdict']]} {dec['verdict']}")
    st.write(proces.motivation.texte.replace("$", "\\$"))
    if proces.motivation.non_verifies:
        st.error("Greffier : chiffres absents des pièces → " + ", ".join(proces.motivation.non_verifies))

st.divider()
st.subheader("Où votre limite est-elle franchie ?")
st.caption(f"Pire baisse observée du portefeuille selon la part placée dans {dossier.ticker} "
           f"({dossier.debut} au {dossier.fin}). Le passé observé, pas une prévision.")
table_courbe = courbe(dossier)
st.altair_chart(graphiques.courbe_taille(table_courbe, dossier.taille, dossier.profil.capital, dossier.ticker),
                width="stretch")
with st.expander("Voir les données du graphique"):
    st.dataframe(pd.DataFrame({
        "Taille": table_courbe["taille"].map(lambda x: pct(x, 0)),
        "Pire baisse observée": table_courbe["pire_baisse"].map(pct),
        "Perte en dollars": (table_courbe["pire_baisse"] * dossier.profil.capital).map(dollars),
        "Cas défavorable sur 12 mois": table_courbe["defavorable_5pct_12_mois"].map(pct),
        f"Part du risque portée par {dossier.ticker}": table_courbe["part_du_risque_du_titre"].map(pct),
    }), hide_index=True)

st.subheader("La salle : qu'est-ce qui changerait le verdict ?")
st.dataframe(pd.DataFrame([{"Hypothèse changée": s["hypothese"], "Verdict": s["verdict"],
                            "Change le verdict": "Oui" if s["change"] else "Non"} for s in proces.salle]),
             hide_index=True)

st.subheader("Les pièces du greffier")
for piece in proces.greffier.pieces:
    with st.expander(f"{piece.numero} — Témoin {piece.temoin} ({temoins.DESCRIPTIONS[piece.temoin]})"):
        st.caption(f"Convoqué par {piece.appele_par} · outil : `{piece.outil}` · {piece.horodatage}")
        st.table(pd.DataFrame({"Valeur": piece.faits}))
        st.write(f"**Source :** {piece.source}")
        st.write(f"**Période :** {piece.periode}")
        st.write(f"**Limites :** {piece.limites}")
