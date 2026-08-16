from __future__ import annotations

import math
from collections import Counter

from ..extensions import db
from ..models import Draw


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
    draws = [draw.numbers for draw in draw_records]
    total = len(draws)
    flat = [n for draw in draws for n in draw]
    freq = Counter(flat)
    for n in range(1, 61):
        freq.setdefault(n, 0)

    sums = [draw.total_sum for draw in draw_records]
    even_counts = [draw.even_count for draw in draw_records]
    consecutive_counts = [draw.consecutive_count for draw in draw_records]

    ranges = {"01-10": 0, "11-20": 0, "21-30": 0, "31-40": 0, "41-50": 0, "51-60": 0}
    for n in flat:
        start = ((n - 1) // 10) * 10 + 1
        ranges[f"{start:02d}-{start+9:02d}"] += 1

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

