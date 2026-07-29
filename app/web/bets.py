"""Rotas de geracao, fechamento e racional de apostas."""

from __future__ import annotations

import math

from functools import lru_cache

from flask import flash, jsonify, redirect, render_template, request, url_for
from werkzeug.datastructures import MultiDict

from ..bets.combinatorics import (
    build_combination_report,
    calculate_individual_filter_targets,
    count_draws_matching_filters,
)
from ..bets.criteria import (
    GENERATION_FILTER_KEYS,
    GENERATION_LIMITS,
    GENERATION_PARAM_KEYS,
    MAX_BET_NUMBERS,
    MIN_BET_NUMBERS,
    GenerationCriteria,
)
from ..bets.service import (
    InvalidClosureNumbersError,
    count_closure_bets,
    generate_bets,
    generate_closure_bets,
    get_generation_bets,
    list_recent_generations_with_bets,
    save_closure_bets,
    save_generated_bets,
)
from ..core.formatting import format_int, format_percent
from ..draws.service import count_draws
from ..settings.service import get_generation_defaults
from . import bp
from .helpers import optional_int, plural

CLOSURE_PREVIEW_LIMIT = 200


def _parse_number_list(value: str | None) -> list[int]:
    """Extrai lista de números a partir de string delimitada.
    
    Args:
        value: String com números separados por vírgula, ponto-e-vírgula ou espaço
        
    Returns:
        Lista de inteiros
        
    Raises:
        InvalidClosureNumbersError: Se algum valor não for número válido
    """
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
            raise InvalidClosureNumbersError(
                f"Dezena inválida: '{part}'. Use apenas números entre 1 e 60."
            )
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
        if MIN_BET_NUMBERS <= len(parsed_numbers) <= MAX_BET_NUMBERS and all(
            1 <= number <= 60 for number in parsed_numbers
        ):
            closure_mode = True
            closure_base_count = len(parsed_numbers)
            quantity = 6
            selected_amount = math.comb(closure_base_count, 6)
            selected_filters = {key: None for key in GENERATION_FILTER_KEYS}
    return quantity, selected_filters, selected_amount, closure_mode, closure_base_count


def _coverage_metrics(
    combination_report: dict, amount: int
) -> tuple[int, float, int | None]:
    coverage_per_bet = combination_report["covered_combinations"]
    covered_by_amount = min(coverage_per_bet * amount, combination_report["remaining"])
    chance_with_amount = (
        (covered_by_amount / combination_report["remaining"])
        if combination_report["remaining"]
        else 0
    )
    chance_with_amount = min(chance_with_amount, 1.0)
    chance_with_amount_one_in = (
        math.ceil(1 / chance_with_amount) if chance_with_amount else None
    )
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

    params = GenerationCriteria.from_mapping(
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
    params = GenerationCriteria(quantity=quantity, amount=amount, **selected_filters)
    return params.query_values()


def _draw_filter_preview_payload(
    selected_filters: dict[str, int | None],
) -> dict[str, int | float | str]:
    count = count_draws_matching_filters(**_active_filters(selected_filters))
    total = count_draws()
    percentage = (count / total) * 100 if total else 0
    return {
        "count": count,
        "total": total,
        "percentage": round(percentage, 2),
        "percentage_text": f"{percentage:.2f}%".replace(".", ","),
    }


@bp.get("/health")
def health_check():
    """Endpoint de verificação de saúde da aplicação."""
    try:
        db.session.execute(db.text("SELECT 1"))
        db_status = "ok"
        status_code = 200
    except Exception as e:
        db_status = f"error: {str(e)}"
        status_code = 503
    
    from ..draws.service import count_draws
    total_draws = count_draws()
    
    return jsonify({
        "status": "healthy" if db_status == "ok" else "unhealthy",
        "database": db_status,
        "total_draws": total_draws
    }), status_code


@bp.route("/rationale")
def rationale():
    closure_numbers = request.args.get("closure_numbers", "")
    quantity, selected_filters, selected_amount = _read_generation_state(request.args)
    return_quantity = quantity
    return_amount = selected_amount
    quantity, selected_filters, selected_amount, closure_mode, closure_base_count = (
        _apply_closure_mode(
            closure_numbers,
            quantity,
            selected_filters,
            selected_amount,
        )
    )
    combination_report = build_combination_report(
        quantity=quantity, filters=selected_filters
    )
    covered_by_amount, chance_with_amount, chance_with_amount_one_in = (
        _coverage_metrics(combination_report, selected_amount)
    )
    return_filters = (
        selected_filters
        if not closure_mode
        else {key: None for key in GENERATION_FILTER_KEYS}
    )
    return_params = _generation_params(return_quantity, return_filters, return_amount)
    if closure_numbers:
        return_params["closure_numbers"] = closure_numbers
    return render_template(
        "bets/rationale.html",
        combination_report=combination_report,
        selected_amount=selected_amount,
        covered_by_amount=covered_by_amount,
        covered_by_amount_formatted=format_int(covered_by_amount),
        chance_with_amount_percent_formatted=format_percent(chance_with_amount * 100),
        chance_with_amount_one_in_formatted=format_int(chance_with_amount_one_in)
        if chance_with_amount_one_in
        else "0",
        closure_mode=closure_mode,
        closure_base_count=closure_base_count,
        selected_filters=selected_filters,
        selected_quantity=quantity,
        return_params=return_params,
    )


@bp.post("/bets/clear")
def clear_bet_generation():
    quantity, _selected_filters, amount = _read_generation_state(request.form)
    flash("Filtros da geração limpos.")
    return redirect(url_for("web.bet_generation", quantity=quantity, amount=amount))


@bp.route("/bets", methods=["GET", "POST"])
def bet_generation():
    bets = []
    closure_total = 0
    closure_preview_truncated = False
    closure_numbers = request.args.get("closure_numbers", "")
    selected_quantity, selected_filters, selected_amount = _read_generation_state(
        request.args
    )
    selected_generation_id = optional_int(request.args.get("generation_id"))
    recent_generations = list_recent_generations_with_bets()
    selected_generation_bets = []
    if selected_generation_id is not None:
        selected_generation_bets = get_generation_bets(selected_generation_id)
    if request.method == "POST":
        action = request.form.get("action", "generate")
        quantity, selected_filters, selected_amount = _read_generation_state(
            request.form
        )
        closure_numbers = request.form.get("closure_numbers", "")
        selected_quantity = quantity
        if closure_numbers.strip() and action == "generate":
            action = "closure"
        if action in {"save", "save_closure"}:
            save_quantity = optional_int(request.form.get("quantity")) or quantity
            try:
                if action == "save_closure":
                    save_quantity = MIN_BET_NUMBERS
                    saved, generation_id = save_closure_bets(
                        _parse_number_list(closure_numbers)
                    )
                else:
                    saved, generation_id = save_generated_bets(
                        quantity=save_quantity,
                        bets=request.form.getlist("bet"),
                    )
            except RuntimeError as exc:
                flash(str(exc))
                return redirect(
                    url_for(
                        "web.bet_generation",
                        **_generation_params(
                            quantity, selected_filters, selected_amount
                        ),
                    )
                )
            flash(
                f"{format_int(saved)} "
                f"{plural(saved, 'aposta gravada', 'apostas gravadas')} no banco de dados."
            )
            if generation_id is not None:
                return redirect(
                    url_for(
                        "web.bet_generation",
                        generation_id=generation_id,
                        **_generation_params(
                            save_quantity, selected_filters, selected_amount
                        ),
                    )
                )
            return redirect(
                url_for(
                    "web.bet_generation",
                    **_generation_params(quantity, selected_filters, selected_amount),
                )
            )

        try:
            if action == "closure":
                base_numbers = _parse_number_list(closure_numbers)
                generated = count_closure_bets(base_numbers)
                bets = generate_closure_bets(
                    base_numbers,
                    limit=CLOSURE_PREVIEW_LIMIT,
                )
                closure_total = generated
                closure_preview_truncated = generated > len(bets)
                flash(
                    f"{format_int(generated)} "
                    f"{plural(generated, 'aposta gerada', 'apostas geradas')} "
                    "pelo fechamento matemático."
                )
            else:
                amount = selected_amount
                generation_filters = _active_filters(selected_filters)
                result = generate_bets(
                    quantity=quantity,
                    amount=amount,
                    persist=False,
                    filters=generation_filters,
                )
                bets = result.bets
                generated = result.generated_count
                if not result.success:
                    flash(
                        f"{generated} {plural(generated, 'aposta gerada', 'apostas geradas')}. "
                        f"Não foi possível atingir {amount} {plural(amount, 'aposta', 'apostas')} "
                        "com os filtros informados."
                    )
                else:
                    flash(
                        f"{generated} {plural(generated, 'aposta gerada', 'apostas geradas')}. "
                        "Revise e escolha se deseja gravar no banco de dados."
                    )
        except InvalidClosureNumbersError as exc:
            flash(str(exc))
        except RuntimeError as exc:
            flash(str(exc))

    filter_preview = _draw_filter_preview_payload(selected_filters)
    (
        selected_quantity,
        selected_filters,
        selected_amount,
        closure_mode,
        closure_base_count,
    ) = _apply_closure_mode(
        closure_numbers,
        selected_quantity,
        selected_filters,
        selected_amount,
    )
    combination_report = build_combination_report(
        quantity=selected_quantity, filters=selected_filters
    )
    covered_by_amount, chance_with_amount, chance_with_amount_one_in = (
        _coverage_metrics(combination_report, selected_amount)
    )
    return render_template(
        "bets/index.html",
        bets=bets,
        closure_total_formatted=format_int(closure_total),
        closure_preview_truncated=closure_preview_truncated,
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
        covered_by_amount_formatted=format_int(covered_by_amount),
        chance_with_amount_percent_formatted=format_percent(chance_with_amount * 100),
        chance_with_amount_one_in_formatted=format_int(chance_with_amount_one_in)
        if chance_with_amount_one_in
        else "0",
        closure_numbers=closure_numbers,
        generation_limits=GENERATION_LIMITS,
        generation_params=_generation_params(
            selected_quantity, selected_filters, selected_amount
        ),
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
    quantity, selected_filters, selected_amount, closure_mode, closure_base_count = (
        _apply_closure_mode(
            closure_numbers,
            quantity,
            selected_filters,
            selected_amount,
        )
    )
    report = build_combination_report(quantity=quantity, filters=selected_filters)
    covered_by_amount, chance_with_amount, chance_with_amount_one_in = (
        _coverage_metrics(report, selected_amount)
    )
    report.update(
        {
            "selected_amount": selected_amount,
            "closure_mode": closure_mode,
            "closure_base_count": closure_base_count,
            "covered_by_amount": covered_by_amount,
            "covered_by_amount_formatted": format_int(covered_by_amount),
            "chance_with_amount_percent": chance_with_amount * 100,
            "chance_with_amount_percent_formatted": format_percent(
                chance_with_amount * 100
            ),
            "chance_with_amount_one_in": chance_with_amount_one_in,
            "chance_with_amount_one_in_formatted": format_int(chance_with_amount_one_in)
            if chance_with_amount_one_in
            else "0",
        }
    )
    return jsonify(report)
