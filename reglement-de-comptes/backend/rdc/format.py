"""Mise en forme des chiffres, identique partout pour que le greffier puisse les vérifier."""
from __future__ import annotations


def pct(x: float, decimales: int = 1) -> str:
    return f"{x * 100:.{decimales}f}".replace(".", ",") + " %"


def dollars(x: float) -> str:
    arrondi = int(round(x / 100.0) * 100)
    return f"{arrondi:,}".replace(",", " ") + " $"


def nombre(x: float, decimales: int = 2) -> str:
    return f"{x:.{decimales}f}".replace(".", ",")


def annees(x: float) -> str:
    return nombre(x, 1) + " an" + ("s" if x >= 2 else "")
