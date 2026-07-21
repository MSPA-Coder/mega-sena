"""Rotas de consulta e importacao de concursos."""

from __future__ import annotations

import logging

from flask import flash, redirect, render_template, request, url_for

from ..draws.importing import import_results_from_xlsx
from ..draws.service import search_contests
from . import bp
from .helpers import optional_int, plural


_ALLOWED_UPLOAD_EXTENSIONS = frozenset({".xlsx"})
_log = logging.getLogger(__name__)


@bp.get("/import")
def import_results():
    """Mantem compatibilidade com a antiga pagina de importacao."""
    return redirect(url_for("web.contests"))


@bp.post("/contests/import")
def import_upload():
    file = request.files.get("file")
    if not file or not file.filename:
        flash("Selecione uma planilha .xlsx para importar.")
        return redirect(url_for("web.contests"))

    extension = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if extension not in _ALLOWED_UPLOAD_EXTENSIONS:
        flash("Formato inválido. Envie apenas planilhas no formato .xlsx.")
        return redirect(url_for("web.contests"))

    file.stream.seek(0)
    try:
        result = import_results_from_xlsx(file.stream)
    except RuntimeError as exc:
        flash(str(exc))
        return redirect(url_for("web.contests"))
    except Exception as exc:
        _log.exception("Erro inesperado na importação: %s", exc)
        flash("Erro inesperado ao processar o arquivo. Verifique se é uma planilha válida.")
        return redirect(url_for("web.contests"))

    imported = result["imported"]
    updated = result["updated"]
    ignored = result["ignored"]
    flash(
        "Importação concluída: "
        f"{imported} {plural(imported, 'novo', 'novos')}, "
        f"{updated} {plural(updated, 'atualizado', 'atualizados')}, "
        f"{ignored} {plural(ignored, 'ignorado', 'ignorados')}."
    )
    return redirect(url_for("web.contests"))


@bp.route("/contests")
def contests():
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
    return render_template(
        "contests/index.html",
        pagination=result.pagination,
        winners_only=result.winners_only,
        consecutive_count=result.consecutive_count,
        even_count=result.even_count,
        active_filters=result.active_filters,
        contests_summary=result.summary,
        pagination_args={key: value for key, value in request.args.items() if key != "page"},
    )
