"""Protecoes HTTP compartilhadas por todas as rotas da aplicacao."""

from __future__ import annotations

import logging
import secrets

from flask import Blueprint, abort, request, session


CSRF_SESSION_KEY = "_csrf_token"
_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'self'; "
    "img-src 'self' data:; "
    "font-src 'self' https://fonts.gstatic.com data:; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "connect-src 'self'; "
    "object-src 'none'"
)

_log = logging.getLogger(__name__)


def csrf_token() -> str:
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
        session.modified = True
    return token


def register_security_hooks(blueprint: Blueprint) -> None:
    """Registra CSRF e headers defensivos no blueprint principal."""

    @blueprint.app_context_processor
    def _inject_security_helpers():
        return {"csrf_token": csrf_token}

    @blueprint.before_app_request
    def _verify_csrf_token():
        if request.method not in _MUTATING_METHODS:
            return None
        expected = session.get(CSRF_SESSION_KEY)
        supplied = request.form.get("_csrf_token") or request.headers.get("X-CSRF-Token")
        if not expected or not supplied or not secrets.compare_digest(str(expected), str(supplied)):
            _log.warning("Requisicao mutante rejeitada por CSRF ausente ou invalido em %s.", request.path)
            abort(400)
        return None

    @blueprint.after_app_request
    def _set_security_headers(response):
        csp = f"{_CONTENT_SECURITY_POLICY}; script-src 'self'"
        response.headers.setdefault("Content-Security-Policy", csp)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        return response
