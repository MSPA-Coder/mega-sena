"""Pequenos helpers compartilhados apenas pela camada HTTP."""

from __future__ import annotations

from typing import Any

from flask import Response, get_flashed_messages, make_response, render_template, request

_MAX_REQUEST_INTEGER = (1 << 63) - 1

#: As quatro severidades que o componente `sharedauth.ui` reconhece. Mesma
#: lista que `sharedauth.ui.SEVERIDADES` -- duplicada aqui porque este módulo
#: não deve depender do pacote de UI (só web/helpers.py x flask).
_SEVERIDADES_VALIDAS = frozenset({"success", "error", "warning", "info"})


def optional_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
        return parsed if -_MAX_REQUEST_INTEGER <= parsed <= _MAX_REQUEST_INTEGER else None
    except ValueError:
        return None


def plural(value: int, singular: str, plural_form: str) -> str:
    return singular if value == 1 else plural_form


def is_htmx_request() -> bool:
    """Return whether the current request was initiated by htmx."""
    return request.headers.get("HX-Request", "").lower() == "true"


def render_vary(template_name: str, **context: Any) -> Response:
    """Renderiza um template marcando a resposta como dependente de `HX-Request`.

    Uma rota e sua variante em fragmento compartilham a mesma URL de propósito,
    para que a navegação normal continue sendo um fallback completo e sem
    JavaScript. O `Vary` impede que um cache intermediário sirva um fragmento
    no lugar do documento inteiro — vale para os dois lados, então página e
    fragmento usam a mesma função.
    """
    response = make_response(render_template(template_name, **context))
    response.vary.add("HX-Request")
    return response


def flashed_avisos() -> list[dict[str, str]]:
    """Mensagens de `flash()` no formato que `data-sa-avisos` espera.

    Resultado de uma navegação de página inteira (POST sem HTMX, seguido de
    redirect) vira toast em vez de banner: é o mesmo "resultado de ação"
    pontual que uma resposta HTMX já mostra por toast, só que chegando por um
    caminho diferente (sessão + redirect em vez de resposta direta). Ver o
    bloco no template base.

    Categoria fora das quatro severidades cai em "info" -- mesma tolerância
    que `sharedauth.ui.svg_icone` já tem para ícone desconhecido.
    """
    mensagens = get_flashed_messages(with_categories=True)
    return [
        {
            "mensagem": mensagem,
            "severidade": categoria if categoria in _SEVERIDADES_VALIDAS else "info",
        }
        for categoria, mensagem in mensagens
    ]
