"""Formatadores usados pela camada de apresentacao.

A formatação de milhar e decimal em pt-BR mora em `sharedauth.formatting`.
Estas funções preservam a assinatura usada pelas rotas e pelos templates e
fixam escolhas de apresentação locais, como o que mostrar quando não há valor.
"""

from __future__ import annotations

from sharedauth.formatting import inteiro, moeda, percentual


def format_int(value: int) -> str:
    """Formata inteiro com separador de milhar brasileiro."""
    return inteiro(value)


def format_percent(value: float) -> str:
    """Formata percentual com ate oito casas e virgula decimal.

    Oito casas, e nao duas: uma chance de 1 em 50 milhoes some inteira com
    duas. Os zeros a direita saem para a coluna nao ficar ilegivel.
    """
    return percentual(value, casas=8, remover_decimal_zero=True, simbolo=False)


def format_brl_without_cents(cents: int | None) -> str:
    """Formata centavos como reais inteiros; premio ausente ou zero fica vazio.

    Vazio, e nao "-": esta funcao alimenta o filtro `brl0` numa coluna onde a
    ausencia de premio e o caso comum, e um traco repetido em toda linha
    poluiria mais que o branco.
    """
    if not cents:
        return ""
    return moeda(round(cents / 100), casas=0, ausente="")
