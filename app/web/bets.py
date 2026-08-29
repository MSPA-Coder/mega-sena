"""Rotas de geracao, fechamento e racional de apostas."""

from __future__ import annotations

import math

from flask import flash, redirect, render_template, request, url_for
from werkzeug.datastructures import MultiDict

from ..bets.combinatorics import (
    TOTAL_DRAW_COMBINATIONS,
    build_combination_report,
    calculate_individual_filter_targets,
    count_distinct_internal_combinations,
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
    count_closure_bets,
    generate_bets,
    generate_closure_bets,
    list_recent_generations_with_bets,
    save_closure_bets,
    save_generated_bets,
)
from ..core.formatting import format_int, format_percent
from ..draws.service import count_draws
from ..settings.service import get_generation_defaults
from . import bp
from .helpers import is_htmx_request, optional_int, plural

CLOSURE_PREVIEW_LIMIT = 200


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
        except ValueError as exc:
            raise RuntimeError(
                "Informe as dezenas do fechamento separadas por espaço, vírgula ou ponto e vírgula."
            ) from exc
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
            selected_filters = dict.fromkeys(GENERATION_FILTER_KEYS)
    return quantity, selected_filters, selected_amount, closure_mode, closure_base_count


def _coverage_metrics(
    combination_report: dict,
    amount: int,
    concrete_bets: list | None = None,
    *,
    exact_combination_count: int | None = None,
) -> dict[str, int | float | str | bool | None]:
    """Descreve a cobertura teórica e, quando calculável, a exata.

    O denominador é sempre C(60, 6): o universo restante depois dos filtros
    não é denominador de probabilidade. Quando a união exata das combinações
    internas não cabe no custo da prévia, resta apenas o limite superior
    teórico, e a interface diz isso explicitamente.
    """
    theoretical_upper = min(
        combination_report["covered_combinations"] * amount,
        TOTAL_DRAW_COMBINATIONS,
    )
    exact_count = exact_combination_count
    if exact_count is None and concrete_bets is not None:
        exact_count = count_distinct_internal_combinations(
            bet.numbers for bet in concrete_bets
        )
    exact_probability = (
        exact_count / TOTAL_DRAW_COMBINATIONS if exact_count is not None else None
    )
    return {
        "theoretical_upper_combinations_formatted": format_int(theoretical_upper),
        "theoretical_upper_probability_percent_formatted": format_percent(
            theoretical_upper / TOTAL_DRAW_COMBINATIONS * 100
        ),
        "exact_coverage_available": exact_count is not None,
        "exact_covered_combinations_formatted": (
            format_int(exact_count) if exact_count is not None else None
        ),
        "exact_probability_percent_formatted": (
            format_percent(exact_probability * 100)
            if exact_probability is not None
            else None
        ),
        "exact_probability_one_in_formatted": (
            format_int(math.ceil(1 / exact_probability)) if exact_probability else "0"
        ),
    }


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


def _preview_context(values: MultiDict) -> dict:
    """Build the read-only preview shown beside the generation form."""
    closure_numbers = values.get("closure_numbers", "")
    quantity, selected_filters, selected_amount = _read_generation_state(values)
    (
        quantity,
        selected_filters,
        selected_amount,
        closure_mode,
        closure_base_count,
    ) = _apply_closure_mode(
        closure_numbers, quantity, selected_filters, selected_amount
    )
    combination_report = build_combination_report(
        quantity=quantity, filters=selected_filters
    )
    coverage_metrics = _coverage_metrics(
        combination_report,
        selected_amount,
        exact_combination_count=(
            math.comb(closure_base_count, 6) if closure_mode else None
        ),
    )
    return {
        "filter_preview": _draw_filter_preview_payload(selected_filters),
        "combination_report": combination_report,
        "selected_quantity": quantity,
        "selected_amount": selected_amount,
        "closure_mode": closure_mode,
        "closure_base_count": closure_base_count,
        "coverage_metrics": coverage_metrics,
    }


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
    coverage_metrics = _coverage_metrics(
        combination_report,
        selected_amount,
        exact_combination_count=(
            math.comb(closure_base_count, 6) if closure_mode else None
        ),
    )
    return_filters = (
        selected_filters
        if not closure_mode
        else dict.fromkeys(GENERATION_FILTER_KEYS)
    )
    return_params = _generation_params(return_quantity, return_filters, return_amount)
    if closure_numbers:
        return_params["closure_numbers"] = closure_numbers
    return render_template(
        "bets/rationale.html",
        combination_report=combination_report,
        selected_amount=selected_amount,
        coverage_metrics=coverage_metrics,
        closure_mode=closure_mode,
        closure_base_count=closure_base_count,
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
    feedback: str | None = None
    htmx_request = is_htmx_request()
    closure_numbers = request.args.get("closure_numbers", "")
    selected_quantity, selected_filters, selected_amount = _read_generation_state(
        request.args
    )
    recent_generations = list_recent_generations_with_bets()
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
                if htmx_request:
                    return render_template(
                        "bets/_generation_result.html",
                        bets=[],
                        feedback=str(exc),
                        avisos=[{"mensagem": str(exc), "severidade": "error"}],
                    )
                flash(str(exc), "error")
                return redirect(
                    url_for(
                        "web.bet_generation",
                        **_generation_params(
                            quantity, selected_filters, selected_amount
                        ),
                    )
                )
            feedback = (
                f"{format_int(saved)} "
                f"{plural(saved, 'aposta gravada', 'apostas gravadas')} no banco de dados."
            )
            if htmx_request:
                return render_template(
                    "bets/_save_response.html",
                    avisos=[{"mensagem": feedback, "severidade": "success"}],
                    recent_generations=list_recent_generations_with_bets(),
                )
            flash(feedback, "success")
            return redirect(
                url_for(
                    "web.bet_generation",
                    **_generation_params(
                        save_quantity if generation_id is not None else quantity,
                        selected_filters,
                        selected_amount,
                    ),
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
                feedback = (
                    f"{format_int(generated)} "
                    f"{plural(generated, 'aposta gerada', 'apostas geradas')} "
                    "pelo fechamento matemático."
                )
            else:
                amount = selected_amount
                generation_filters = _active_filters(selected_filters)
                bets = generate_bets(
                    quantity=quantity,
                    amount=amount,
                    filters=generation_filters,
                )
                generated = len(bets)
                if generated < amount:
                    feedback = (
                        f"{generated} {plural(generated, 'aposta gerada', 'apostas geradas')}. "
                        f"Não foi possível atingir {amount} {plural(amount, 'aposta', 'apostas')} "
                        "com os filtros informados."
                    )
                else:
                    feedback = (
                        f"{generated} {plural(generated, 'aposta gerada', 'apostas geradas')}. "
                        "Revise e escolha se deseja gravar no banco de dados."
                    )
        except RuntimeError as exc:
            feedback = str(exc)

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
    coverage_metrics = _coverage_metrics(
        combination_report,
        selected_amount,
        bets if bets else None,
        exact_combination_count=(
            math.comb(closure_base_count, 6) if closure_mode else None
        ),
    )
    context = {
        "bets": bets,
        "closure_total_formatted": format_int(closure_total),
        "closure_preview_truncated": closure_preview_truncated,
        "recent_generations": recent_generations,
        "filter_preview": filter_preview,
        "combination_report": combination_report,
        "selected_filters": selected_filters,
        "selected_quantity": selected_quantity,
        "selected_amount": selected_amount,
        "closure_mode": closure_mode,
        "closure_base_count": closure_base_count,
        "coverage_metrics": coverage_metrics,
        "closure_numbers": closure_numbers,
        "generation_limits": GENERATION_LIMITS,
        "generation_params": _generation_params(
            selected_quantity, selected_filters, selected_amount
        ),
        "feedback": feedback,
    }
    if htmx_request:
        # Sem `flash()` aqui de propósito: o `feedback` de gerar/fechamento já
        # é conteúdo da própria seção `#generation-result` (o resumo fica ao
        # lado das apostas geradas, para quem decide se grava), não um aviso
        # avulso -- duplicá-lo em toast só repetiria a mesma frase duas vezes
        # na tela. O `context` abaixo é reaproveitado por `bets/index.html`,
        # que inclui este mesmo parcial dentro de `<main>`.
        return render_template("bets/_generation_result.html", **context)
    return render_template(
        "bets/index.html",
        **context,
    )


@bp.get("/bets/preview")
def bet_preview():
    """Return the server-rendered read-only generation preview for htmx."""
    return render_template("bets/_preview.html", **_preview_context(request.args))


@bp.get("/bets/filter-targets/fragment")
def filter_targets_fragment():
    target_percentage = request.args.get("target_percentage", 80, type=float)
    target_percentage = max(0, min(target_percentage, 100))
    targets = calculate_individual_filter_targets(target_percentage)
    response = render_template(
        "bets/_filter_targets.html",
        target_percentage=target_percentage,
        targets=targets,
    )
    response.headers["HX-Trigger-After-Settle"] = "bets-preview"
    return response
