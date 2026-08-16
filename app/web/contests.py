"""Rotas de consulta e importação de concursos."""

from __future__ import annotations

import logging

from flask import flash, redirect, request, url_for

from ..draws.importing import import_results_from_xlsx
from ..draws.service import search_contests
from . import bp
from .helpers import is_htmx_request, optional_int, plural, render_vary

_ALLOWED_UPLOAD_EXTENSIONS = frozenset({".xlsx"})
_log = logging.getLogger(__name__)


def _contests_context() -> dict:
    page = max(1, request.args.get("page", 1, type=int) or 1)
    winners_only = request.args.get("winners_only") == "1"
    consecutive_count = optional_int(request.args.get("consecutive_count"))
    even_count = optional_int(request.args.get("even_count"))
    result = search_contests(
        page=page,
        winners_only=winners_only,
        consecutive_count=consecutive_count,
        even_count=even_count,
    )
    return {
        "pagination": result.pagination,
        "winners_only": result.winners_only,
        "consecutive_count": result.consecutive_count,
        "even_count": result.even_count,
        "active_filters": result.active_filters,
        "contests_summary": result.summary,
        "pagination_args": {
            key: value for key, value in request.args.items() if key != "page"
        },
    }


def _import_feedback(message: str):
    if is_htmx_request():
        return render_vary(
            "contests/_import_response.html", message=message, **_contests_context()
        )
    flash(message)
    return redirect(url_for("web.contests"))


@bp.post("/contests/import")
def import_upload():
    file = request.files.get("file")
    if not file or not file.filename:
        return _import_feedback("Selecione uma planilha .xlsx para importar.")

    extension = (
        "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    )
    if extension not in _ALLOWED_UPLOAD_EXTENSIONS:
        return _import_feedback("Formato inválido. Envie apenas planilhas no formato .xlsx.")

    file.stream.seek(0)
    try:
        result = import_results_from_xlsx(file.stream)
    except RuntimeError as exc:
        return _import_feedback(str(exc))
    except Exception as exc:
        _log.exception("Erro inesperado na importação: %s", exc)
        return _import_feedback(
            "Erro inesperado ao processar o arquivo. Verifique se é uma planilha válida."
        )

    imported = result["imported"]
    updated = result["updated"]
    ignored = result["ignored"]
    return _import_feedback(
        "Importação concluída: "
        f"{imported} {plural(imported, 'novo', 'novos')}, "
        f"{updated} {plural(updated, 'atualizado', 'atualizados')}, "
        f"{ignored} {plural(ignored, 'ignorado', 'ignorados')}."
    )


@bp.route("/contests")
def contests():
    context = _contests_context()
    if is_htmx_request():
        return render_vary("contests/_results.html", **context)
    return render_vary("contests/index.html", **context)
