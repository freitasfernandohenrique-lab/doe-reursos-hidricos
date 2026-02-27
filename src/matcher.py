"""Detecção de palavras-chave, contexto, classificação e deduplicação."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import Any


KEYWORD_ALIASES = {
    "saneamento": ["saneamento"],
    "saneago": ["saneago"],
    "recursos hidricos": ["recursos hídricos", "recursos hidricos"],
    "agua": ["água", "agua"],
    "esgoto": ["esgoto"],
    "drenagem": ["drenagem"],
    "residuos": ["resíduos", "residuos"],
    "estacao de tratamento": ["estação de tratamento", "estacao de tratamento"],
    "eta": ["eta"],
    "ete": ["ete"],
    "outorga": ["outorga"],
    "captacao": ["captação", "captacao", "captação de água", "captacao de agua"],
    "tarifa": ["tarifa"],
    "contrato": ["contrato", "aditivo"],
    "licitacao": ["licitação", "licitacao", "concorrência", "concorrencia", "pregão", "pregao", "dispensa", "inexigibilidade"],
}

THEME_RULES = {
    "licitacoes_contratos": ["licitacao", "contrato"],
    "outorgas_recursos_hidricos": ["outorga", "captacao", "recursos hidricos", "agua"],
    "obras_servicos": ["saneamento", "esgoto", "drenagem", "estacao de tratamento", "eta", "ete", "residuos"],
    "regulacao_tarifas": ["tarifa", "saneago"],
    "comunicados": [],
}

ORG_PATTERNS = [
    re.compile(r"\bSANEAGO\b", re.IGNORECASE),
    re.compile(r"\bAGENCIA GOIANA DE REGULACAO\b|\bAGR\b", re.IGNORECASE),
    re.compile(r"\bSECRETARIA\s+DE\s+MEIO\s+AMBIENTE\b|\bSEMAD\b", re.IGNORECASE),
    re.compile(r"\bSECRETARIA\s+DA\s+INFRAESTRUTURA\b|\bSEINFRA\b", re.IGNORECASE),
    re.compile(r"\bPREFEITURA\s+MUNICIPAL\s+DE\s+([A-ZÀ-Ú\s]+)\b", re.IGNORECASE),
]

MONEY_OR_DEADLINE_RE = re.compile(
    r"(R\$\s?\d[\d\.,]*|\b\d{1,3}(?:\.\d{3})*(?:,\d{2})?\s*(?:reais|dias|meses|anos)\b)",
    re.IGNORECASE,
)


@dataclass(slots=True)
class MatchItem:
    unique_id: str
    date_iso: str
    edition_id: int
    edition_numero: int | None
    suplemento: int
    keyword: str
    keyword_group: str
    context: str
    score: int
    theme: str
    orgao: str
    link: str
    source_type: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize(value: str) -> str:
    no_accents = "".join(
        c for c in unicodedata.normalize("NFD", value) if unicodedata.category(c) != "Mn"
    )
    return no_accents.lower()


def _compile_patterns() -> list[tuple[str, str, re.Pattern[str]]]:
    patterns: list[tuple[str, str, re.Pattern[str]]] = []
    for group, aliases in KEYWORD_ALIASES.items():
        for alias in aliases:
            norm = _normalize(alias)
            escaped = re.escape(norm)
            # bordas de palavra para reduzir falso positivo.
            pattern = re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)
            patterns.append((group, alias, pattern))
    return patterns


PATTERNS = _compile_patterns()


def _extract_context(text: str, start: int, end: int, min_chars: int = 300, max_chars: int = 600) -> str:
    length = len(text)
    center = (start + end) // 2
    half = max(min_chars // 2, 150)
    left = max(0, center - half)
    right = min(length, center + half)

    while right - left < min_chars and (left > 0 or right < length):
        if left > 0:
            left -= 1
        if right < length:
            right += 1

    if right - left > max_chars:
        right = left + max_chars
    return text[left:right].strip()


def infer_theme(groups: set[str]) -> str:
    for theme, members in THEME_RULES.items():
        if members and any(member in groups for member in members):
            return theme
    return "comunicados"


def infer_orgao(context: str) -> str:
    snippet = context[:1200]
    for pattern in ORG_PATTERNS:
        m = pattern.search(snippet)
        if m:
            return m.group(0).strip()
    return "Não inferido"


def compute_score(keyword_groups: set[str], context: str) -> int:
    score = 0
    if "licitacao" in keyword_groups:
        score += 3
    if "saneago" in keyword_groups:
        score += 2
    if any(k in keyword_groups for k in ("outorga", "captacao", "recursos hidricos")):
        score += 2
    if MONEY_OR_DEADLINE_RE.search(context):
        score += 1
    if "contrato" in keyword_groups:
        score += 1
    return score


def _uid(link: str, context: str, keyword_group: str) -> str:
    base = f"{link}|{keyword_group}|{_normalize(context[:200])}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def find_matches(edition: dict[str, Any], text: str, source_type: str) -> list[MatchItem]:
    if not text:
        return []

    normalized = _normalize(text)
    by_context: dict[int, dict[str, Any]] = defaultdict(dict)

    for group, alias, pattern in PATTERNS:
        for match in pattern.finditer(normalized):
            start, end = match.span()
            key = start // 250
            bucket = by_context[key]
            bucket.setdefault("groups", set()).add(group)
            bucket.setdefault("aliases", set()).add(alias)
            if "start" not in bucket or start < bucket["start"]:
                bucket["start"] = start
            if "end" not in bucket or end > bucket["end"]:
                bucket["end"] = end

    items: list[MatchItem] = []
    seen: set[str] = set()

    for data in by_context.values():
        start = data["start"]
        end = data["end"]
        context = _extract_context(text, start, end)
        groups = set(data["groups"])
        aliases = sorted(data["aliases"])
        keyword_display = ", ".join(aliases[:3])
        theme = infer_theme(groups)
        orgao = infer_orgao(context)
        score = compute_score(groups, context)
        link = edition.get("pdf_url") or edition.get("html_url") or ""
        unique_id = _uid(link, context, theme)
        if unique_id in seen:
            continue
        seen.add(unique_id)
        items.append(
            MatchItem(
                unique_id=unique_id,
                date_iso=edition["date_iso"],
                edition_id=int(edition["id"]),
                edition_numero=edition.get("numero"),
                suplemento=int(edition.get("suplemento") or 0),
                keyword=keyword_display,
                keyword_group=",".join(sorted(groups)),
                context=context,
                score=score,
                theme=theme,
                orgao=orgao,
                link=link,
                source_type=source_type,
            )
        )

    # Dedupe final por link + inicio do contexto
    dedup: dict[str, MatchItem] = {}
    for item in items:
        k = f"{item.link}|{_normalize(item.context[:160])}"
        if k not in dedup or item.score > dedup[k].score:
            dedup[k] = item
    return list(dedup.values())
