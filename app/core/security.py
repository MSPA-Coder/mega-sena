"""Protecoes HTTP compartilhadas por todas as rotas da aplicacao.

`Flask-WTF` (`csrf` em `app/extensions.py`) verifica todo metodo mutante e
expoe `csrf_token()` aos templates.

Os valores dos cabecalhos defensivos e da CSP vem de `sharedauth.security`.
A excecao de `img-src` continua sendo uma decisao local deste projeto.
"""

from __future__ import annotations

from flask import Blueprint
from sharedauth.security import SECURITY_HEADERS, montar_csp, registrar_cabecalhos

__all__ = ["SECURITY_HEADERS", "register_security_hooks"]

# A politica da biblioteca fecha `img-src` em 'self', e este projeto agora
# cabe nela. A folga existia por um motivo unico: o favicon era um SVG
# embutido no proprio `<link rel="icon">`. Ele passou a ser
# `static/favicon.svg`, um arquivo como qualquer outro, e a excecao deixou de
# ter razao de ser -- era a unica ocorrencia de URI `data:` no projeto.
#
# Os graficos do dashboard NAO precisam de folga nenhuma: a altura de cada
# barra vem de uma classe `.pct-N` estatica em `dashboard-charts.css`/
# `components.css`, uma por porcentagem inteira de 0 a 100 -- o servidor
# calcula a porcentagem e escolhe a classe; nada muda estilo em runtime. Nem
# `style="--count: N"` e `element.style.setProperty()` via JS nao sao
# permitidos por `style-src 'self'`.
_IMAGENS_DATA_URI = False

CONTENT_SECURITY_POLICY = montar_csp(imagens_data_uri=_IMAGENS_DATA_URI)


def register_security_hooks(blueprint: Blueprint) -> None:
    """Registra os cabecalhos defensivos no blueprint principal."""
    registrar_cabecalhos(blueprint, imagens_data_uri=_IMAGENS_DATA_URI)
