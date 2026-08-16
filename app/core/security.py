"""Protecoes HTTP compartilhadas por todas as rotas da aplicacao.

O CSRF nao mora mais aqui: `Flask-WTF` (`csrf` em `app/extensions.py`) verifica
todo metodo mutante e expoe `csrf_token()` aos templates. Uma implementacao
propria de CSRF e exatamente o tipo de codigo de seguranca que nao compensa
manter quando existe uma biblioteca estabelecida fazendo o mesmo.
"""

from __future__ import annotations

from flask import Blueprint

# A política é fechada em 'self', sem nenhuma exceção: nenhuma origem externa,
# nenhum estilo ou script inline.
#
# Os gráficos do dashboard chegavam a precisar de `style="--count: N"` para dar
# altura às barras. Os valores passaram a viajar em `data-css-var` /
# `data-css-value`, aplicados por `app/static/base.js`. A alternativa seria
# abrir `style-src-attr 'unsafe-inline'`, que o Firefox não implementa — lá a
# política cairia de volta para `style-src` e as barras ficariam sem altura.
_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "style-src 'self'; "
    "connect-src 'self'; "
    "object-src 'none'"
)

# Conjunto defensivo comum aos quatro projetos do mantenedor. Manter igual em
# todos é o que permite auditar um e confiar nos demais.
#
# `Referrer-Policy` é `same-origin`, não `no-referrer`: sob `no-referrer` o
# navegador serializa o cabeçalho `Origin` como `null` também em POST de mesma
# origem (Fetch spec), e qualquer verificação de CSRF que consulte `Origin` —
# como a do Django, no projeto irmão — passa a recusar a requisição com o token
# correto. `same-origin` não vaza referrer para fora da origem, que é o que
# importa, e preserva o `Origin`.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "X-Permitted-Cross-Domain-Policies": "none",
}


def register_security_hooks(blueprint: Blueprint) -> None:
    """Registra os cabecalhos defensivos no blueprint principal."""

    @blueprint.after_app_request
    def _set_security_headers(response):
        csp = f"{_CONTENT_SECURITY_POLICY}; script-src 'self'"
        response.headers.setdefault("Content-Security-Policy", csp)
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response
