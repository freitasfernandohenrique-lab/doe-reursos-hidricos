"""Agregações e métricas para resumo diário (somente dia atual)."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from .matcher import MatchItem


def _sort_items(items: list[MatchItem]) -> list[MatchItem]:
    return sorted(items, key=lambda x: (x.score, x.date_iso, x.edition_id), reverse=True)


def analyze(items_today_raw: list[MatchItem], today_iso: str) -> dict[str, Any]:
    all_sorted = _sort_items(items_today_raw)
    today_items = [i for i in all_sorted if i.date_iso == today_iso]

    keyword_counter = Counter()
    theme_counter = Counter()
    link_counter = Counter(i.link for i in today_items)

    for item in today_items:
        for group in item.keyword_group.split(","):
            if group.strip():
                keyword_counter[group.strip()] += 1
        theme_counter[item.theme] += 1

    recurring = 0
    new_items = 0
    for item in today_items:
        if link_counter[item.link] > 1:
            recurring += 1
        else:
            new_items += 1

    top_day = today_items[:5]
    top_today = today_items[:10]

    return {
        "generated_at": datetime.now().isoformat(),
        "today_iso": today_iso,
        "counts": {
            "items_today": len(today_items),
            "new_items": new_items,
            "recurring_items": recurring,
        },
        "top_day": [i.to_dict() for i in top_day],
        "today_items": [i.to_dict() for i in today_items],
        "top_today": [i.to_dict() for i in top_today],
        "keywords_today": dict(keyword_counter.most_common()),
        "themes_today": dict(theme_counter.most_common()),
    }
