from __future__ import annotations

import logging
import math
from collections import Counter
from itertools import combinations

from ..core.numbers import draw_parameters
from ..extensions import db
from ..models import Config, Draw

_log = logging.getLogger(__name__)
_DRAW_PARAMETERS_VERSION_KEY = "_draw_parameters_version"
_DRAW_PARAMETERS_VERSION = "1"


def all_draw_numbers() -> list[list[int]]:
    rows = db.session.query(Draw.n1, Draw.n2, Draw.n3, Draw.n4, Draw.n5, Draw.n6).order_by(Draw.contest).all()
    return [list(row) for row in rows]


def build_stats(count: int | None = None) -> dict:
    """
    Monta o conjunto de estatísticas exibidas no dashboard.

    Se `count` for informado, considera apenas os `count` concursos mais
    recentes (por número de concurso). Se for None, considera todo o
    histórico — comportamento padrão usado no carregamento inicial da página.
    """
    query = Draw.query.order_by(Draw.contest.desc())
    if count is not None:
        query = query.limit(count)
    draw_records = query.all()
    draw_records.reverse()  # ordem cronológica ascendente, igual ao comportamento original
    draws = [draw.numbers for draw in draw_records]
    total = len(draws)
    flat = [n for draw in draws for n in draw]
    freq = Counter(flat)
    for n in range(1, 61):
        freq.setdefault(n, 0)

    pair_counter = Counter()
    trio_counter = Counter()
    sums, even_counts = [], []
    consecutive_counts = []
    last_seen = {n: None for n in range(1, 61)}
    for idx, draw_record in enumerate(draw_records, start=1):
        numbers = draw_record.numbers
        pair_counter.update(combinations(numbers, 2))
        trio_counter.update(combinations(numbers, 3))
        sums.append(draw_record.total_sum)
        even_counts.append(draw_record.even_count)
        consecutive_counts.append(draw_record.consecutive_count)
        for n in numbers:
            last_seen[n] = idx

    delays = {n: total - last_seen[n] if last_seen[n] else total for n in range(1, 61)}
    ranges = {"01-10": 0, "11-20": 0, "21-30": 0, "31-40": 0, "41-50": 0, "51-60": 0}
    for n in flat:
        start = ((n - 1) // 10) * 10 + 1
        ranges[f"{start:02d}-{start+9:02d}"] += 1

    sum_distribution = dict(sorted(Counter(sums).items()))
    sum_histogram = _build_sum_histogram(sums)
    even_distribution = dict(sorted(Counter(even_counts).items()))
    consecutive_distribution = dict(sorted(Counter(consecutive_counts).items()))

    prize_cards = {
        "mega_sena": {
            "label": "Mega Sena",
            "games": sum(1 for draw in draw_records if draw.winners_6 > 0),
            "winners": sum(draw.winners_6 for draw in draw_records),
        },
        "quina": {
            "label": "Quina",
            "games": sum(1 for draw in draw_records if draw.winners_5 > 0),
            "winners": sum(draw.winners_5 for draw in draw_records),
        },
        "quadra": {
            "label": "Quadra",
            "games": sum(1 for draw in draw_records if draw.winners_4 > 0),
            "winners": sum(draw.winners_4 for draw in draw_records),
        },
    }
    mega_sena_games_with_winners = prize_cards["mega_sena"]["games"]
    mega_sena_games_without_winners = total - mega_sena_games_with_winners
    mega_sena_games_with_winners_pct = round((mega_sena_games_with_winners / total) * 100, 1) if total else 0
    mega_sena_games_without_winners_pct = round((mega_sena_games_without_winners / total) * 100, 1) if total else 0

    return {
        "total_draws": total,
        "count": count,
        "actual_count": total,
        "mega_sena_games_with_winners": mega_sena_games_with_winners,
        "mega_sena_games_without_winners": mega_sena_games_without_winners,
        "mega_sena_games_with_winners_pct": mega_sena_games_with_winners_pct,
        "mega_sena_games_without_winners_pct": mega_sena_games_without_winners_pct,
        "frequency": dict(sorted(freq.items())),
        "most_frequent": freq.most_common(10),
        "least_frequent": sorted(freq.items(), key=lambda kv: (kv[1], kv[0]))[:10],
        "top_pairs": pair_counter.most_common(10),
        "top_trios": trio_counter.most_common(10),
        "delays": sorted(delays.items(), key=lambda kv: (-kv[1], kv[0]))[:15],
        "ranges": ranges,
        "avg_sum": round(sum(sums) / len(sums), 2) if sums else 0,
        "avg_even": round(sum(even_counts) / len(even_counts), 2) if even_counts else 0,
        "sum_distribution": sum_distribution,
        "sum_histogram": sum_histogram,
        "even_distribution": even_distribution,
        "consecutive_distribution": consecutive_distribution,
        "last_contest": draw_records[-1] if draw_records else None,
        "prize_cards": prize_cards,
    }


def _build_sum_histogram(sums: list[int], bin_size: int = 10) -> dict:
    if not sums:
        return {"bins": [], "max_frequency": 0, "y_ticks": [0]}

    first_bin = (min(sums) // bin_size) * bin_size
    last_bin = math.ceil((max(sums) + 1) / bin_size) * bin_size
    counter = Counter(((total - first_bin) // bin_size) * bin_size + first_bin for total in sums)
    max_frequency = max(counter.values()) if counter else 0
    tick_step = max(1, math.ceil(max_frequency / 4 / 10) * 10)
    y_ticks = list(range(0, tick_step * 5, tick_step))
    scale_max = y_ticks[-1]

    bins = []
    for start in range(first_bin, last_bin, bin_size):
        end = start + bin_size - 1
        bins.append(
            {
                "start": start,
                "end": end,
                "count": counter.get(start, 0),
                "x_label": start if start % 50 == 0 else "",
            }
        )
    return {"bins": bins, "max_frequency": scale_max, "y_ticks": y_ticks}


def refresh_draw_parameters(*, commit: bool = True) -> int:
    total_draws = Draw.query.count()
    if total_draws == 0:
        return 0

    updated = 0
    for draw in Draw.query.all():
        derived = draw_parameters(draw.numbers)
        changed = False
        for key, value in derived.items():
            if getattr(draw, key) != value:
                setattr(draw, key, value)
                changed = True
        if changed:
            updated += 1
    if updated and commit:
        db.session.commit()
        _log.info("refresh_draw_parameters: %d/%d concursos recalculados.", updated, total_draws)
    return updated


def ensure_draw_parameters_current(*, commit: bool = True) -> int:
    """Executa a atualização derivada uma vez por versão, em vez de a cada boot."""
    marker = Config.query.filter_by(key=_DRAW_PARAMETERS_VERSION_KEY).one_or_none()
    if marker and marker.value == _DRAW_PARAMETERS_VERSION:
        return 0
    updated = refresh_draw_parameters(commit=False)
    if marker is None:
        db.session.add(Config(key=_DRAW_PARAMETERS_VERSION_KEY, value=_DRAW_PARAMETERS_VERSION))
    else:
        marker.value = _DRAW_PARAMETERS_VERSION
    if commit:
        db.session.commit()
    return updated
