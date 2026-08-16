"""Formatadores usados pela camada de apresentacao."""

from __future__ import annotations


def format_int(value: int) -> str:
    """Formata inteiro com separador de milhar brasileiro."""
    return f"{value:,}".replace(",", ".")


def format_percent(value: float) -> str:
    """Formata percentual com ate oito casas e virgula decimal."""
    return f"{value:.8f}".rstrip("0").rstrip(".").replace(".", ",")


def format_brl_without_cents(cents: int | None) -> str:
    """Formata centavos como reais inteiros."""
    if not cents:
        return ""
    value = round(cents / 100)
    formatted = f"{value:,}".replace(",", ".")
    return f"R$ {formatted}"
