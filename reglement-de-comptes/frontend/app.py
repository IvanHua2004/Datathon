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

from rdc import donnees, temoins, intention, scenarios, comparaison, rapport_pdf
from rdc.format import dollars, pct
from rdc.profils import PROFILS
from rdc.proces import (V_COMPATIBLE, V_CONTRAINTE, V_INDECIDABLE, V_TENSION, courbe,
                        ouvrir_proces, lancer_proces_stream)

# Charger automatiquement le fichier .env si présent
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    for ligne in env_path.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith("#") and "=" in ligne:
            k, v = ligne.split("=", 1)
            os.environ[k.strip()] = v.strip().strip('"').strip("'")

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
    cle = st.selectbox("Investisseur (fictif)", list(PROFILS), format_func=lambda c: PROFILS[c].nom)
    profil = PROFILS[cle]
    st.write(profil.resume)
    st.write(f"**Objectif :** {profil.objectif}")
    st.write(f"**Préférences :** {profil.preferences}")
    st.write(f"**Capital (hypothèse) :** {dollars(profil.capital)}")
    st.write(f"**Budget de perte (hypothèse) :** {pct(profil.budget_perte, 0)}")

    st.header("La demande")
    titres = list(d.univers.index)

    intention_texte = st.text_input(
        "Votre volonté libre",
        value="",
        placeholder="Ex : devrais acheter +30% dans des etf ? ou 20% NVDA",
        help="Tapez librement ce que vous souhaitez faire. L'IA interprète l'actif et le pourcentage."
    )

    if intention_texte.strip():
        t_int, s_int, expl_int = intention.interpreter_intention(intention_texte, d.univers, profil)
        st.info(expl_int)
        idx_ticker = titres.index(t_int) if t_int in titres else titres.index(profil.demande_exemple[0])
        val_taille = s_int
    else:
        idx_ticker = titres.index(profil.demande_exemple[0])
        val_taille = profil.demande_exemple[1]

    ticker = st.selectbox("Titre à ajouter", titres, index=idx_ticker,
                          format_func=lambda t: f"{t} — {d.univers.loc[t, 'name']}")
    taille = st.select_slider("Part du portefeuille à y placer", options=[0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50],
                              value=val_taille, format_func=lambda x: pct(x, 0))
    mode = st.radio("Agents", ["gabarit", "bedrock"],
                    format_func=lambda m: {"gabarit": "Sans modèle (gabarits)", "bedrock": "Amazon Bedrock (Strands / Claude)"}[m],
                    help="Le mode Bedrock exige des identifiants AWS et un modèle activé.")

    with st.expander("🔑 Configuration AWS Bedrock", expanded=(mode == "bedrock")):
        st.caption("Identifiants AWS (depuis « Get AWS CLI credentials » dans Workshop Studio).")
        in_key = st.text_input("AWS Access Key ID", value=os.environ.get("AWS_ACCESS_KEY_ID", ""), type="password")
        in_secret = st.text_input("AWS Secret Access Key", value=os.environ.get("AWS_SECRET_ACCESS_KEY", ""), type="password")
        in_token = st.text_input("AWS Session Token (temporaire)", value=os.environ.get("AWS_SESSION_TOKEN", ""), type="password")
        in_region = st.text_input("Région AWS", value=os.environ.get("AWS_REGION", "us-east-1"))
        in_model = st.text_input("Model ID Bedrock", value=os.environ.get("BEDROCK_MODEL_ID", "global.anthropic.claude-sonnet-5"))

        if st.button("Valider & Tester la connexion", use_container_width=True):
            if in_key: os.environ["AWS_ACCESS_KEY_ID"] = in_key
            if in_secret: os.environ["AWS_SECRET_ACCESS_KEY"] = in_secret
            if in_token: os.environ["AWS_SESSION_TOKEN"] = in_token
            if in_region: os.environ["AWS_REGION"] = in_region
            if in_model: os.environ["BEDROCK_MODEL_ID"] = in_model
            try:
                import boto3
                bclient = boto3.client("bedrock-runtime", region_name=in_region)
                resp = bclient.converse(
                    modelId=in_model,
                    messages=[{"role": "user", "content": [{"text": "Réponds exactement : Prêt."}]}],
                    inferenceConfig={"maxTokens": 10}
                )
                mot = resp["output"]["message"]["content"][0]["text"].strip()
                st.success(f"✅ Connecté à Bedrock ({in_model}) ! Réponse : {mot}")
            except Exception as e:
                st.error(f"❌ Erreur Bedrock : {type(e).__name__} : {e}")

    lancer = st.button("⚖️ Ouvrir le procès", type="primary", width="stretch")
    st.caption("Données : " + (f"Amazon S3, bucket `{SOURCE_S3}`" if SOURCE_S3 else "fichiers locaux")
               + f" · Région AWS : {os.environ.get('AWS_REGION') or 'us-east-1'}")

if lancer:
    st.session_state["decision_investisseur"] = None
    st.session_state["afficher_scenarios"] = False
    st.session_state["intention_texte"] = intention_texte

    st.subheader("🏛️ Audience en direct du Tribunal d'AlphaForge")
    with st.status("Le tribunal siège et procède à l'audition...", expanded=True) as status:
        for event in lancer_proces_stream(profil, ticker, taille, mode, intention_texte=intention_texte):
            if event["etape"] == "HUISSIER":
                st.markdown(f"**📢 {event['acteur']}** : *{event['texte']}*")
            elif event["etape"] == "TEMOIN":
                st.markdown(f"**⚖️ {event['acteur']}** ({event['titre']}) : {event['texte']}")
            elif event["etape"] == "DEFENSE":
                st.markdown(f"**💼 {event['acteur']}** : {event['texte']}")
            elif event["etape"] == "PROCUREUR":
                st.markdown(f"**🛡️ {event['acteur']}** : {event['texte']}")
            elif event["etape"] == "JUGE":
                st.markdown(f"**👨‍⚖️ {event['acteur']}** : **{event['texte']}**")
                st.session_state["proces"] = event["proces"]
        status.update(label="Audience terminée — Jugement rendu !", state="complete", expanded=False)

proces = st.session_state.get("proces")
if proces is None:
    st.info("Choisissez un investisseur et formulez une demande, puis ouvrez le procès.")
    st.subheader("Portefeuille actuel (fictif)")
    st.dataframe(pd.DataFrame({"Poids": {t: pct(p / sum(profil.portefeuille.values()))
                                         for t, p in profil.portefeuille.items()}}))
    st.stop()

dossier, dec = proces.dossier, proces.decision
if proces.avertissement:
    st.warning(proces.avertissement)

st.subheader(f"📋 Carte de Décision : {dossier.profil.nom} demande {pct(dossier.taille, 0)} dans {dossier.ticker}")

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

# Section Décision Arbitrale (Oui / Non) et Scénarios
st.subheader("🎯 Votre arbitrage d'investisseur : quelle est votre décision ?")
st.caption("Le tribunal éclaire les risques, mais le libre arbitre appartient à l'investisseur. Quel est votre choix ?")

col_oui, col_non, col_scen = st.columns([1, 1, 1.2])
if col_oui.button("👍 OUI — J'investis quand même", type="primary", use_container_width=True):
    st.session_state["decision_investisseur"] = True
if col_non.button("🛑 NON — Je renonce au projet", use_container_width=True):
    st.session_state["decision_investisseur"] = False
if col_scen.button("💡 D'autres scénarios ?", use_container_width=True):
    st.session_state["afficher_scenarios"] = True

# Affichage de l'analyse comparative si décision prise
if st.session_state.get("decision_investisseur") is not None:
    choix = st.session_state["decision_investisseur"]
    comp = comparaison.comparer_decision(dossier, dec, choix)
    
    st.markdown(f"### ⚖️ {comp.titre_decision}")
    st.info(f"**Statut :** {comp.statut_conformite}\n\n{comp.commentaire_conseil}")
    
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("Perte max historique", dollars(comp.perte_max_dollars), delta=dollars(comp.delta_perte_dollars) if choix else None, delta_color="inverse")
    col_m2.metric("Volatilité finale", pct(comp.volatilite_finale), delta=pct(comp.delta_volatilite) if choix else None, delta_color="inverse")
    col_m3.metric("Temps de recouvrement", comp.temps_recuperation)
    col_m4.metric("Dépassement budget", dollars(comp.montant_depassement) if comp.budget_depasse else "0 $")
    
    st.markdown("**Recommandations du Conseil :**")
    for reco in comp.recommandations:
        st.write(f"- {reco}")

# Affichage des scénarios alternatifs si demandés
if st.session_state.get("afficher_scenarios"):
    st.markdown("### 💡 Scénarios Alternatifs Conçus par le Tribunal")
    intention_cur = st.session_state.get("intention_texte", "")
    alts = scenarios.generer_scenarios_alternatifs(dossier, dec, intention_cur)
    st.session_state["alternatives"] = alts
    
    for alt in alts:
        with st.expander(f"**{alt['nom']}** — {alt['verdict']}", expanded=True):
            st.write(alt["description"])
            st.caption(alt["pourquoi"])
            c1, c2, c3 = st.columns(3)
            c1.metric("Pire baisse", pct(alt["pire_baisse"]))
            c2.metric("Perte en dollars", dollars(alt["perte_dollars"]))
            c3.metric("Volatilité", pct(alt["volatilite"]))

# Bouton de téléchargement du PDF officiel
st.divider()
pdf_data = rapport_pdf.generer_pdf_rapport(
    proces,
    decision_investisseur=st.session_state.get("decision_investisseur"),
    scenarios_alternatifs=st.session_state.get("alternatives"),
    intention_texte=st.session_state.get("intention_texte", "")
)
st.download_button(
    label="📄 Télécharger la Carte de Décision Auditée (PDF Officiel du Greffier)",
    data=pdf_data,
    file_name=f"Carte_Decision_AlphaForge_{profil.nom}_{dossier.ticker}.pdf",
    mime="application/pdf",
    type="secondary"
)

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
