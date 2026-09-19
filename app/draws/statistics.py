from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable

from ..extensions import db
from ..models import Draw

STATS_FETCH_BATCH_SIZE = 1_000


def all_draw_numbers() -> list[list[int]]:
    rows = (
        db.session.query(Draw.n1, Draw.n2, Draw.n3, Draw.n4, Draw.n5, Draw.n6)
        .order_by(Draw.contest)
        .yield_per(STATS_FETCH_BATCH_SIZE)
    )
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
    rows = query.with_entities(
        Draw.n1,
        Draw.n2,
        Draw.n3,
        Draw.n4,
        Draw.n5,
        Draw.n6,
        Draw.total_sum,
        Draw.even_count,
        Draw.consecutive_count,
        Draw.winners_6,
        Draw.winners_5,
        Draw.winners_4,
    ).yield_per(STATS_FETCH_BATCH_SIZE)

    total = 0
    freq = Counter(dict.fromkeys(range(1, 61), 0))
    ranges = {"01-10": 0, "11-20": 0, "21-30": 0, "31-40": 0, "41-50": 0, "51-60": 0}
    sums: Counter[int] = Counter()
    even_distribution_counter: Counter[int] = Counter()
    consecutive_distribution_counter: Counter[int] = Counter()
    prize_games = {"mega_sena": 0, "quina": 0, "quadra": 0}
    prize_winners = {"mega_sena": 0, "quina": 0, "quadra": 0}

    for row in rows:
        numbers = list(row[:6])
        total += 1
        for number in numbers:
            freq[number] += 1
            start = ((number - 1) // 10) * 10 + 1
            ranges[f"{start:02d}-{start+9:02d}"] += 1
        sums[row.total_sum] += 1
        even_distribution_counter[row.even_count] += 1
        consecutive_distribution_counter[row.consecutive_count] += 1
        for key, winners in (
            ("mega_sena", row.winners_6),
            ("quina", row.winners_5),
            ("quadra", row.winners_4),
        ):
            prize_winners[key] += winners
            prize_games[key] += winners > 0

    sum_histogram = _build_sum_histogram(sums)
    even_distribution = dict(sorted(even_distribution_counter.items()))
    consecutive_distribution = dict(sorted(consecutive_distribution_counter.items()))

    prize_cards = {
        "mega_sena": {
            "label": "Mega Sena",
            "games": prize_games["mega_sena"],
            "winners": prize_winners["mega_sena"],
        },
        "quina": {
            "label": "Quina",
            "games": prize_games["quina"],
            "winners": prize_winners["quina"],
        },
        "quadra": {
            "label": "Quadra",
            "games": prize_games["quadra"],
            "winners": prize_winners["quadra"],
        },
    }
    mega_sena_games_with_winners = prize_cards["mega_sena"]["games"]
    mega_sena_games_without_winners = total - mega_sena_games_with_winners
    mega_sena_games_with_winners_pct = round((mega_sena_games_with_winners / total) * 100, 1) if total else 0
    mega_sena_games_without_winners_pct = round((mega_sena_games_without_winners / total) * 100, 1) if total else 0

    return {
        "total_draws": total,
        "actual_count": total,
        "mega_sena_games_with_winners": mega_sena_games_with_winners,
        "mega_sena_games_without_winners": mega_sena_games_without_winners,
        "mega_sena_games_with_winners_pct": mega_sena_games_with_winners_pct,
        "mega_sena_games_without_winners_pct": mega_sena_games_without_winners_pct,
        "frequency": dict(sorted(freq.items())),
        "most_frequent": freq.most_common(10),
        "least_frequent": sorted(freq.items(), key=lambda kv: (kv[1], kv[0]))[:10],
        "ranges": ranges,
        "sum_histogram": sum_histogram,
        "even_distribution": even_distribution,
        "consecutive_distribution": consecutive_distribution,
        "prize_cards": prize_cards,
    }


def _build_sum_histogram(sums: Iterable[int], bin_size: int = 10) -> dict:
    counter = Counter(sums)
    if not counter:
        return {"bins": [], "max_frequency": 0, "y_ticks": [0]}

    first_bin = (min(counter) // bin_size) * bin_size
    last_bin = math.ceil((max(counter) + 1) / bin_size) * bin_size
    binned_counter: Counter[int] = Counter()
    for total, frequency in counter.items():
        start = ((total - first_bin) // bin_size) * bin_size + first_bin
        binned_counter[start] += frequency
    max_frequency = max(binned_counter.values()) if binned_counter else 0
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
                "count": binned_counter.get(start, 0),
                "x_label": start if start % 50 == 0 else "",
            }
        )
    return {"bins": bins, "max_frequency": scale_max, "y_ticks": y_ticks}
