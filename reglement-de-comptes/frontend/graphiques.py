"""Graphique de la courbe « taille de la position → pire baisse observée »."""
from __future__ import annotations

import altair as alt
import pandas as pd

BLEU = "#2a78d6"
ENCRE = "#0b0b0b"
ENCRE_SECONDAIRE = "#52514e"
TITRE_X = "Part du portefeuille placée dans le titre (%)"
TITRE_Y = "Pire baisse observée du portefeuille (%)"


def courbe_taille(df: pd.DataFrame, taille_demandee: float, capital: float, ticker: str) -> alt.Chart:
    d = pd.DataFrame({
        "Taille de la position (%)": df["taille"] * 100,
        "Pire baisse observée (%)": df["pire_baisse"] * 100,
        "Perte en dollars": (df["pire_baisse"] * capital).round(-2),
        f"Part du risque portée par {ticker} (%)": (df["part_du_risque_du_titre"] * 100).round(1),
    })
    budget = float(df["budget_perte"].iloc[0]) * 100
    x = alt.X("Taille de la position (%):Q", title=TITRE_X, axis=alt.Axis(grid=False, tickMinStep=5))
    y = alt.Y("Pire baisse observée (%):Q", title=TITRE_Y, scale=alt.Scale(zero=True),
              axis=alt.Axis(gridColor="#e8e7e3", domain=False))
    infobulle = [alt.Tooltip(c, format=",.1f") for c in d.columns if c != "Perte en dollars"]
    infobulle.insert(2, alt.Tooltip("Perte en dollars", format=",.0f"))

    ligne = alt.Chart(d).mark_line(color=BLEU, strokeWidth=2).encode(x=x, y=y)
    points = alt.Chart(d).mark_point(color=BLEU, filled=True, size=90, opacity=1,
                                     stroke="#fcfcfb", strokeWidth=2).encode(x=x, y=y, tooltip=infobulle)
    demande = d[(d["Taille de la position (%)"] - taille_demandee * 100).abs() < 1e-6]
    repere = alt.Chart(demande).mark_point(color=ENCRE, size=320, strokeWidth=2, filled=False).encode(x=x, y=y)
    etiquette = alt.Chart(demande.assign(texte="Demande")).mark_text(
        dx=-14, dy=16, align="right", color=ENCRE, fontSize=12).encode(x=x, y=y, text="texte")
    seuil = pd.DataFrame({"x": [float(d["Taille de la position (%)"].max())], "y": [budget],
                          "texte": [f"Budget de perte déclaré : {budget:.0f} %"]})
    y_seuil = alt.Y("y:Q", title=TITRE_Y)
    regle = alt.Chart(seuil).mark_rule(color=ENCRE_SECONDAIRE, strokeDash=[6, 4], strokeWidth=1.5).encode(y=y_seuil)
    # étiquette à droite, là où la courbe est loin de la ligne du budget
    texte_regle = alt.Chart(seuil).mark_text(align="right", dx=-4, dy=-9, color=ENCRE_SECONDAIRE,
                                             fontSize=12).encode(x=alt.X("x:Q", title=TITRE_X), y=y_seuil, text="texte")
    return (ligne + regle + texte_regle + points + repere + etiquette).properties(height=320)
