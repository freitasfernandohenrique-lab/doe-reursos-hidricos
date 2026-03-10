"""Agregações e métricas por eixo para o resumo diário e a janela recente."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from .matcher import MatchItem


AXIS_LABELS = {
    "microrregioes_saneamento_basico": "Microrregiões de saneamento básico",
    "recursos_hidricos_geral": "Recursos hídricos geral",
}


def _sort_items(items: list[MatchItem]) -> list[MatchItem]:
    return sorted(items, key=lambda x: (x.score, x.date_iso, x.edition_id), reverse=True)


def _serialize_items(items: list[MatchItem]) -> list[dict[str, Any]]:
    return [item.to_dict() for item in items]


def _build_axis_summary(items: list[MatchItem], limit: int = 10) -> dict[str, Any]:
    keyword_counter = Counter()
    theme_counter = Counter()
    orgao_counter = Counter()

    for item in items:
        for group in item.keyword_group.split(","):
            if group.strip():
                keyword_counter[group.strip()] += 1
        theme_counter[item.theme] += 1
        orgao_counter[item.orgao] += 1

    return {
        "count": len(items),
        "top_items": _serialize_items(items[:limit]),
        "keywords": dict(keyword_counter.most_common()),
        "themes": dict(theme_counter.most_common()),
        "orgaos": dict(orgao_counter.most_common(5)),
    }


def analyze(items_raw: list[MatchItem], today_iso: str, window_days: int = 5) -> dict[str, Any]:
    all_sorted = _sort_items(items_raw)
    today_items = [item for item in all_sorted if item.date_iso == today_iso]

    sections: dict[str, Any] = {}
    for axis, label in AXIS_LABELS.items():
        axis_today = [item for item in today_items if item.monitor_axis == axis]
        axis_window = [item for item in all_sorted if item.monitor_axis == axis]
        sections[axis] = {
            "label": label,
            "today": _build_axis_summary(axis_today, limit=10),
            "window": _build_axis_summary(axis_window, limit=20),
        }

    return {
        "generated_at": datetime.now().isoformat(),
        "today_iso": today_iso,
        "window_days": window_days,
        "counts": {
            "items_today": len(today_items),
            "items_window": len(all_sorted),
        },
        "today_items": _serialize_items(today_items),
        "window_items": _serialize_items(all_sorted),
        "sections": sections,
    }
