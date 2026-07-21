from __future__ import annotations

import logging
import math

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from werkzeug.datastructures import MultiDict

from .core.security import register_security_hooks
from .extensions import db
from .generation_params import GENERATION_FILTER_KEYS, GENERATION_PARAM_KEYS, GenerationParams
from .models import Draw, GeneratedBet
from .services import (
    build_combination_report,
    build_recent_frequency,
    build_stats,
    calculate_individual_filter_targets,
    count_draws_matching_filters,
    format_int,
    format_percent,
    generate_bets,
    generate_closure_bets,
    get_config_values,
    get_generation_defaults,
    import_results_from_xlsx,
    list_recent_generations_with_bets,
    save_generated_bets,
    update_config_values,
)

bp = Blueprint("web", __name__)
_MAX_REQUEST_INTEGER = (1 << 63) - 1

_log = logging.getLogger(__name__)

_ALLOWED_UPLOAD_EXTENSIONS = frozenset({".xlsx"})


def _plural(value: int, singular: str, plural: str) -> str:
    return singular if value == 1 else plural


register_security_hooks(bp)


# Aliases locais para os formatadores importados de services
def _format_int(value: int) -> str:
    return format_int(value)


def _format_chance_percentage(value: float) -> str:
    return format_percent(value)


@bp.get("/")
def home():
    return redirect(url_for("web.dashboard"))


@bp.get("/dashboard")
def dashboard():
    stats = build_stats()
    return render_template("dashboard.html", stats=stats)


@bp.get("/import")
def import_results():
    """Compatibilidade: a página de importação foi movida para a aba Concursos."""
    return redirect(url_for("web.contests"))


@bp.get("/settings")
def settings_page():
    return render_template("settings.html", config_values=get_config_values())


@bp.post("/contests/import")
def import_upload():
    file = request.files.get("file")
    if not file or not file.filename:
        flash("Selecione uma planilha .xlsx para importar.")
        return redirect(url_for("web.contests"))

    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in _ALLOWED_UPLOAD_EXTENSIONS:
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
        f"{imported} {_plural(imported, 'novo', 'novos')}, "
        f"{updated} {_plural(updated, 'atualizado', 'atualizados')}, "
        f"{ignored} {_plural(ignored, 'ignorado', 'ignorados')}."
    )
    return redirect(url_for("web.contests"))


@bp.post("/settings")
def save_settings():
    update_config_values(request.form)
    _log.info("Configurações de geração atualizadas.")
    flash("Configurações salvas.")
    return redirect(url_for("web.settings_page"))


@bp.post("/reset")
def reset_database():
    bet_count = GeneratedBet.query.count()
    draw_count = Draw.query.count()
    GeneratedBet.query.delete()
    Draw.query.delete()
    db.session.commit()
    _log.warning("Base reiniciada: %d concursos e %d apostas apagados.", draw_count, bet_count)
    flash("Base reiniciada: concursos e apostas apagados.")
    return redirect(url_for("web.settings_page"))


@bp.route("/rationale")
def rationale():
    closure_numbers = request.args.get("closure_numbers", "")
    quantity, selected_filters, selected_amount = _read_generation_state(request.args)
    return_quantity = quantity
    return_amount = selected_amount
    quantity, selected_filters, selected_amount, closure_mode, closure_base_count = _apply_closure_mode(
        closure_numbers,
        quantity,
        selected_filters,
        selected_amount,
    )
    combination_report = build_combination_report(quantity=quantity, filters=selected_filters)
    covered_by_amount, chance_with_amount, chance_with_amount_one_in = _coverage_metrics(combination_report, selected_amount)
    return_filters = selected_filters if not closure_mode else {key: None for key in GENERATION_FILTER_KEYS}
    return_params = _generation_params(return_quantity, return_filters, return_amount)
    if closure_numbers:
        return_params["closure_numbers"] = closure_numbers
    return render_template(
        "rationale.html",
        combination_report=combination_report,
        selected_amount=selected_amount,
        covered_by_amount=covered_by_amount,
        covered_by_amount_formatted=_format_int(covered_by_amount),
        chance_with_amount_percent_formatted=_format_chance_percentage(chance_with_amount * 100),
        chance_with_amount_one_in_formatted=_format_int(chance_with_amount_one_in) if chance_with_amount_one_in else "0",
        closure_mode=closure_mode,
        closure_base_count=closure_base_count,
        selected_filters=selected_filters,
        selected_quantity=quantity,
        return_params=return_params,
    )


def _optional_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
        return parsed if -_MAX_REQUEST_INTEGER <= parsed <= _MAX_REQUEST_INTEGER else None
    except ValueError:
        return None


def _parse_number_list(value: str | None) -> list[int]:
    if not value:
        return []
    normalized = value.replace(";", ",").replace(" ", ",")
    numbers = []
    for part in normalized.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            numbers.append(int(part))
        except ValueError:
            raise RuntimeError("Informe as dezenas do fechamento separadas por espaço, vírgula ou ponto e vírgula.")
    return numbers


def _apply_closure_mode(
    closure_numbers: str,
    quantity: int,
    selected_filters: dict[str, int | None],
    selected_amount: int,
) -> tuple[int, dict[str, int | None], int, bool, int]:
    closure_mode = False
    closure_base_count = 0
    if closure_numbers.strip():
        try:
            parsed_numbers = sorted(set(_parse_number_list(closure_numbers)))
        except RuntimeError:
            parsed_numbers = []
        if 6 <= len(parsed_numbers) <= 15 and all(1 <= number <= 60 for number in parsed_numbers):
            closure_mode = True
            closure_base_count = len(parsed_numbers)
            quantity = 6
            selected_amount = math.comb(closure_base_count, 6)
            selected_filters = {key: None for key in GENERATION_FILTER_KEYS}
    return quantity, selected_filters, selected_amount, closure_mode, closure_base_count


def _coverage_metrics(combination_report: dict, amount: int) -> tuple[int, float, int | None]:
    coverage_per_bet = combination_report["covered_combinations"]
    covered_by_amount = min(coverage_per_bet * amount, combination_report["remaining"])
    chance_with_amount = (covered_by_amount / combination_report["remaining"]) if combination_report["remaining"] else 0
    chance_with_amount = min(chance_with_amount, 1.0)
    chance_with_amount_one_in = math.ceil(1 / chance_with_amount) if chance_with_amount else None
    return covered_by_amount, chance_with_amount, chance_with_amount_one_in


def _read_generation_state(values: MultiDict) -> tuple[int, dict[str, int | None], int]:
    defaults = get_generation_defaults()
    has_url_state = any(key in values for key in GENERATION_PARAM_KEYS)
    if has_url_state:
        source = MultiDict(
            {
                "quantity": values.get("quantity", str(defaults["bet_quantity"])),
                "amount": values.get("amount", str(defaults["generation_amount"])),
            }
        )
        for key in GENERATION_FILTER_KEYS:
            source[key] = values.get(key, "")
    else:
        source = MultiDict(
            {
                "quantity": str(defaults["bet_quantity"]),
                "amount": str(defaults["generation_amount"]),
            }
        )
        for key in GENERATION_FILTER_KEYS:
            value = defaults.get(key)
            source[key] = "" if value is None else str(value)

    params = GenerationParams.from_mapping(
        source,
        default_quantity=int(defaults["bet_quantity"] or 6),
        default_amount=int(defaults["generation_amount"] or 5),
    )
    selected_filters = params.filters(include_empty=True)
    return params.quantity, selected_filters, params.amount


def _active_filters(selected_filters: dict[str, int | None]) -> dict[str, int]:
    return {key: value for key, value in selected_filters.items() if value is not None}


def _generation_params(
    quantity: int,
    selected_filters: dict[str, int | None],
    amount: int,
) -> dict[str, int | str]:
    params = GenerationParams(quantity=quantity, amount=amount, **selected_filters)
    return params.query_values()


def _format_percentage(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def _draw_filter_preview_payload(selected_filters: dict[str, int | None]) -> dict[str, int | float | str]:
    count = count_draws_matching_filters(**_active_filters(selected_filters))
    total = Draw.query.count()
    percentage = (count / total) * 100 if total else 0
    return {
        "count": count,
        "total": total,
        "percentage": round(percentage, 2),
        "percentage_text": f"{_format_percentage(percentage)}%",
    }


@bp.post("/bets/clear")
def clear_bet_generation():
    quantity, _selected_filters, amount = _read_generation_state(request.form)
    flash("Filtros da geração limpos.")
    return redirect(url_for("web.bet_generation", quantity=quantity, amount=amount))


@bp.route("/bets", methods=["GET", "POST"])
def bet_generation():
    bets = []
    closure_numbers = request.args.get("closure_numbers", "")
    selected_quantity, selected_filters, selected_amount = _read_generation_state(request.args)
    selected_generation_id = _optional_int(request.args.get("generation_id"))
    recent_generations = list_recent_generations_with_bets()
    selected_generation_bets = []
    if selected_generation_id is not None:
        selected_generation_bets = (
            GeneratedBet.query.filter(GeneratedBet.generation_id == selected_generation_id)
            .order_by(GeneratedBet.id)
            .all()
        )
    if request.method == "POST":
        action = request.form.get("action", "generate")
        quantity, selected_filters, selected_amount = _read_generation_state(request.form)
        closure_numbers = request.form.get("closure_numbers", "")
        selected_quantity = quantity
        if closure_numbers.strip() and action == "generate":
            action = "closure"
        if action == "save":
            save_quantity = _optional_int(request.form.get("quantity")) or quantity
            try:
                saved, generation_id = save_generated_bets(quantity=save_quantity, bets=request.form.getlist("bet"))
            except RuntimeError as exc:
                flash(str(exc))
                return redirect(url_for("web.bet_generation", **_generation_params(quantity, selected_filters, selected_amount)))
            flash(f"{saved} {_plural(saved, 'aposta gravada', 'apostas gravadas')} no banco de dados.")
            if generation_id is not None:
                return redirect(url_for("web.bet_generation", generation_id=generation_id, **_generation_params(save_quantity, selected_filters, selected_amount)))
            return redirect(url_for("web.bet_generation", **_generation_params(quantity, selected_filters, selected_amount)))

        try:
            if action == "closure":
                bets = generate_closure_bets(_parse_number_list(closure_numbers))
                generated = len(bets)
                flash(f"{generated} {_plural(generated, 'aposta gerada', 'apostas geradas')} pelo fechamento matemático.")
            else:
                amount = selected_amount
                generation_filters = _active_filters(selected_filters)
                bets = generate_bets(quantity=quantity, amount=amount, persist=False, filters=generation_filters)
                if len(bets) < amount:
                    generated = len(bets)
                    flash(
                        f"{generated} {_plural(generated, 'aposta gerada', 'apostas geradas')}. "
                        f"Não foi possível atingir {amount} {_plural(amount, 'aposta', 'apostas')} com os filtros informados."
                    )
                else:
                    generated = len(bets)
                    flash(f"{generated} {_plural(generated, 'aposta gerada', 'apostas geradas')}. Revise e escolha se deseja gravar no banco de dados.")
        except RuntimeError as exc:
            flash(str(exc))
    filter_preview = _draw_filter_preview_payload(selected_filters)
    selected_quantity, selected_filters, selected_amount, closure_mode, closure_base_count = _apply_closure_mode(
        closure_numbers,
        selected_quantity,
        selected_filters,
        selected_amount,
    )
    combination_report = build_combination_report(quantity=selected_quantity, filters=selected_filters)
    covered_by_amount, chance_with_amount, chance_with_amount_one_in = _coverage_metrics(combination_report, selected_amount)
    return render_template(
        "bets.html",
        bets=bets,
        recent_generations=recent_generations,
        selected_generation_bets=selected_generation_bets,
        selected_generation_id=selected_generation_id,
        filter_preview=filter_preview,
        combination_report=combination_report,
        selected_filters=selected_filters,
        selected_quantity=selected_quantity,
        selected_amount=selected_amount,
        closure_mode=closure_mode,
        closure_base_count=closure_base_count,
        covered_by_amount_formatted=_format_int(covered_by_amount),
        chance_with_amount_percent_formatted=_format_chance_percentage(chance_with_amount * 100),
        chance_with_amount_one_in_formatted=_format_int(chance_with_amount_one_in) if chance_with_amount_one_in else "0",
        closure_numbers=closure_numbers,
        generation_params=_generation_params(selected_quantity, selected_filters, selected_amount),
    )


@bp.get("/api/draw-filter-preview")
def draw_filter_preview():
    _quantity, selected_filters, _amount = _read_generation_state(request.args)
    return jsonify(_draw_filter_preview_payload(selected_filters))


@bp.get("/api/filter-targets")
def filter_targets():
    target_percentage = request.args.get("target_percentage", 80, type=float)
    return jsonify(calculate_individual_filter_targets(target_percentage))


@bp.get("/api/combinations")
def combinations():
    quantity, selected_filters, selected_amount = _read_generation_state(request.args)
    closure_numbers = request.args.get("closure_numbers", "")
    quantity, selected_filters, selected_amount, closure_mode, closure_base_count = _apply_closure_mode(
        closure_numbers,
        quantity,
        selected_filters,
        selected_amount,
    )
    report = build_combination_report(quantity=quantity, filters=selected_filters)
    covered_by_amount, chance_with_amount, chance_with_amount_one_in = _coverage_metrics(report, selected_amount)
    report.update(
        {
            "selected_amount": selected_amount,
            "closure_mode": closure_mode,
            "closure_base_count": closure_base_count,
            "covered_by_amount": covered_by_amount,
            "covered_by_amount_formatted": _format_int(covered_by_amount),
            "chance_with_amount_percent": chance_with_amount * 100,
            "chance_with_amount_percent_formatted": _format_chance_percentage(chance_with_amount * 100),
            "chance_with_amount_one_in": chance_with_amount_one_in,
            "chance_with_amount_one_in_formatted": _format_int(chance_with_amount_one_in) if chance_with_amount_one_in else "0",
        }
    )
    return jsonify(report)


@bp.get("/api/recent-frequency")
def recent_frequency():
    raw = request.args.get("count", "").strip()
    count = _optional_int(raw) if raw else None
    if count is not None:
        count = max(10, min(count, 10_000))
    data = build_recent_frequency(count)
    return jsonify(data)


@bp.get("/api/dashboard-stats")
def dashboard_stats():
    """
    Payload completo para atualização do dashboard inteiro de acordo com um
    período (quantidade de concursos mais recentes). Usado pelo seletor de
    período global, que afeta todos os cards e gráficos da página.
    """
    raw = request.args.get("count", "").strip()
    count = _optional_int(raw) if raw else None
    if count is not None:
        count = max(10, min(count, 10_000))

    stats = build_stats(count)
    payload = {
        "count": stats["count"],
        "actual_count": stats["actual_count"],
        "total_draws": stats["total_draws"],
        "mega_sena_games_with_winners": stats["mega_sena_games_with_winners"],
        "mega_sena_games_without_winners": stats["mega_sena_games_without_winners"],
        "mega_sena_games_with_winners_pct": stats["mega_sena_games_with_winners_pct"],
        "mega_sena_games_without_winners_pct": stats["mega_sena_games_without_winners_pct"],
        "prize_cards": stats["prize_cards"],
        "even_distribution": stats["even_distribution"],
        "consecutive_distribution": stats["consecutive_distribution"],
        "ranges": stats["ranges"],
        "most_frequent": stats["most_frequent"],
        "least_frequent": stats["least_frequent"],
        "frequency": stats["frequency"],
        "sum_histogram": stats["sum_histogram"],
    }
    return jsonify(payload)


@bp.route("/contests")
def contests():
    page = max(1, request.args.get("page", 1, type=int) or 1)
    winners_only = request.args.get("winners_only") == "1"
    consecutive_count = _optional_int(request.args.get("consecutive_count"))
    even_count = _optional_int(request.args.get("even_count"))
    query = Draw.query
    active_filters = []
    if winners_only:
        query = query.filter(Draw.winners_6 > 0)
    if consecutive_count is not None:
        consecutive_count = max(0, min(consecutive_count, 6))
        query = query.filter(Draw.consecutive_count == consecutive_count)
        active_filters.append(f"maior sequência de números consecutivos = {consecutive_count}")
    if even_count is not None:
        even_count = max(0, min(even_count, 6))
        query = query.filter(Draw.even_count == even_count)
        active_filters.append(f"quantidade de números pares = {even_count}")
    pagination = query.order_by(Draw.contest.desc()).paginate(page=page, per_page=50, error_out=False)
    if winners_only:
        contests_summary = (
            f"{pagination.total} concurso com acertadores na Mega Sena encontrado."
            if pagination.total == 1
            else f"{pagination.total} concursos com acertadores na Mega Sena encontrados."
        )
    elif active_filters:
        contests_summary = (
            f"{pagination.total} concurso encontrado."
            if pagination.total == 1
            else f"{pagination.total} concursos encontrados."
        )
    else:
        contests_summary = (
            f"{pagination.total} concurso importado."
            if pagination.total == 1
            else f"{pagination.total} concursos importados."
        )
    return render_template(
        "contests.html",
        pagination=pagination,
        winners_only=winners_only,
        consecutive_count=consecutive_count,
        even_count=even_count,
        active_filters=active_filters,
        contests_summary=contests_summary,
        pagination_args={key: value for key, value in request.args.items() if key != "page"},
    )
