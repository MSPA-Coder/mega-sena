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


def render_htmx(template_name: str, **context: Any) -> Response:
    """Render an HTML fragment and keep shared URL responses cache-safe.

    Full-page routes and their htmx fragment variants deliberately share URLs so
    normal navigation remains a complete, JavaScript-free fallback.  ``Vary``
    prevents an intermediary cache from serving a fragment as a document.
    """
    response = make_response(render_template(template_name, **context))
    response.vary.add("HX-Request")
    return response


def render_page(template_name: str, **context: Any) -> Response:
    """Render the full-page variant of a route that also serves fragments."""
    response = make_response(render_template(template_name, **context))
    response.vary.add("HX-Request")
    return response
