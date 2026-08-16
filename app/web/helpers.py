"""Pequenos helpers compartilhados apenas pela camada HTTP."""

from __future__ import annotations

from typing import Any

from flask import Response, make_response, render_template, request

_MAX_REQUEST_INTEGER = (1 << 63) - 1


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
