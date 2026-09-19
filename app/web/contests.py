"""Rotas de consulta e importação de concursos."""

from __future__ import annotations

import logging

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..audit.service import record_event
from ..draws.downloading import ResultsDownloadError, fetch_results_xlsx
from ..draws.importing import import_results_from_xlsx
from ..draws.service import search_contests
from ..extensions import db
from ..settings.service import get_results_source_url
from . import bp
from .helpers import audit_request_context, is_htmx_request, optional_int, plural

_ALLOWED_UPLOAD_EXTENSIONS = frozenset({".xlsx"})
_log = logging.getLogger(__name__)


def _safe_upload_name(filename: str) -> str:
    """Guarda só um nome de arquivo inofensivo como metadado de proveniência."""
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    return (name or "upload.xlsx")[:255]


def _record_import_failure(*, source: str) -> None:
    # Uma falha de importação já desfez a transação dos concursos. O evento de
    # falha é deliberadamente separado para não desaparecer junto com ela.
    db.session.rollback()
    try:
        record_event(
            action="draws.import",
            entity="draw",
            actor=current_user,
            success=False,
            context=audit_request_context(source=source),
        )
    except Exception:
        _log.exception("Não foi possível registrar a falha da importação.")


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


def _import_feedback(message: str, *, severidade: str = "error"):
    if is_htmx_request():
        return render_template(
            "contests/_import_response.html",
            avisos=[{"mensagem": message, "severidade": severidade}],
            **_contests_context(),
        )
    flash(message, severidade)
    return redirect(url_for("web.contests"))


def _import_result_feedback(result: dict[str, int], *, source: str) -> object:
    imported = result["imported"]
    updated = result["updated"]
    ignored = result["ignored"]
    return _import_feedback(
        f"Importação {source} concluída: "
        f"{imported} {plural(imported, 'novo', 'novos')}, "
        f"{updated} {plural(updated, 'atualizado', 'atualizados')}, "
        f"{ignored} {plural(ignored, 'ignorado', 'ignorados')}.",
        severidade="success",
    )


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
        result = import_results_from_xlsx(
            file.stream,
            provenance={
                "source_type": "manual_upload",
                "source_name": _safe_upload_name(file.filename),
            },
            audit={
                "action": "draws.import",
                "entity": "draw",
                "actor": current_user,
                "context": audit_request_context(source="upload"),
            },
        )
    except RuntimeError as exc:
        _record_import_failure(source="upload")
        return _import_feedback(str(exc))
    except Exception as exc:
        _log.exception("Erro inesperado na importação: %s", exc)
        _record_import_failure(source="upload")
        return _import_feedback(
            "Erro inesperado ao processar o arquivo. Verifique se é uma planilha válida."
        )

    return _import_result_feedback(result, source="manual")


@bp.post("/contests/import-link")
def import_from_link():
    try:
        source_url = get_results_source_url()
        source = fetch_results_xlsx(source_url)
        result = import_results_from_xlsx(
            source,
            provenance={"source_type": "official_link", "source_url": source_url},
            audit={
                "action": "draws.import",
                "entity": "draw",
                "actor": current_user,
                "context": audit_request_context(source="link"),
            },
        )
    except ResultsDownloadError as exc:
        _record_import_failure(source="link")
        return _import_feedback(str(exc))
    except RuntimeError as exc:
        _record_import_failure(source="link")
        return _import_feedback(str(exc))
    except Exception as exc:
        _log.exception("Erro inesperado na importação pelo link: %s", exc)
        _record_import_failure(source="link")
        return _import_feedback(
            "Erro inesperado ao obter a planilha. Verifique o link configurado."
        )

    return _import_result_feedback(result, source="pelo link")


@bp.route("/contests")
def contests():
    context = _contests_context()
    if is_htmx_request():
        return render_template("contests/_results.html", **context)
    return render_template("contests/index.html", **context)
