"""Protecoes HTTP compartilhadas por todas as rotas da aplicacao.

O CSRF nao mora mais aqui: `Flask-WTF` (`csrf` em `app/extensions.py`) verifica
todo metodo mutante e expoe `csrf_token()` aos templates. Uma implementacao
propria de CSRF e exatamente o tipo de codigo de seguranca que nao compensa
manter quando existe uma biblioteca estabelecida fazendo o mesmo.

Os cabecalhos defensivos e a CSP tambem sairam daqui, pela mesma razao e um
passo adiante: os valores vinham de um dicionario mantido igual a mao em dois
projetos -- com o comentario "manter igual em todos" copiado junto -- e mesmo
assim as copias divergiram. Agora vem de `sharedauth.security`, e o unico
detalhe que continua sendo decisao deste projeto e a excecao de `img-src`.
"""

from __future__ import annotations

from flask import Blueprint
from sharedauth.security import SECURITY_HEADERS, montar_csp, registrar_cabecalhos

__all__ = ["SECURITY_HEADERS", "register_security_hooks"]

# A politica da biblioteca fecha `img-src` em 'self'. Este projeto precisa de
# `data:` por um motivo unico e verificavel: o favicon do `base.html` e um SVG
# embutido no proprio `<link rel="icon">`, nao um arquivo estatico.
#
# Os graficos do dashboard NAO precisam de folga nenhuma: a altura de cada
# barra vem de uma classe `.pct-N` estatica em `dashboard-charts.css`/
# `components.css`, uma por porcentagem inteira de 0 a 100 -- o servidor
# calcula a porcentagem e escolhe a classe; nada muda estilo em runtime. Nem
# `style="--count: N"` nem `element.style.setProperty()` via JS funcionariam
# sob `style-src 'self'`, e foi assim que o dashboard quebrou uma vez.
_IMAGENS_DATA_URI = True

CONTENT_SECURITY_POLICY = montar_csp(imagens_data_uri=_IMAGENS_DATA_URI)


def register_security_hooks(blueprint: Blueprint) -> None:
    """Registra os cabecalhos defensivos no blueprint principal."""
    registrar_cabecalhos(blueprint, imagens_data_uri=_IMAGENS_DATA_URI)
