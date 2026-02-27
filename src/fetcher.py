"""Coleta de edições do DOE-GO via endpoints oficiais."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL_DEFAULT = "https://diariooficial.abc.go.gov.br"
INDEX_URL_DEFAULT = f"{BASE_URL_DEFAULT}/"


@dataclass(slots=True)
class Edition:
    id: int
    date_iso: str
    numero: int | None
    suplemento: int
    suplemento_nome: str
    tipo_edicao_nome: str
    pages: int | None
    pdf_url: str
    html_url: str
    jornal_url: str
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["raw"] = self.raw
        return data


def _session(timeout: int = 30) -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(
        {
            "User-Agent": "doego-monitor/1.0 (+github-actions)",
            "Accept": "application/json,text/html,application/pdf,*/*",
        }
    )
    session.request_timeout = timeout  # type: ignore[attr-defined]
    return session


def _get_json(session: requests.Session, url: str) -> dict[str, Any]:
    resp = session.get(url, timeout=getattr(session, "request_timeout", 30))
    resp.raise_for_status()
    return resp.json()


def _parse_date_ddmmyyyy(value: str) -> date:
    return datetime.strptime(value, "%d/%m/%Y").date()


def discover_editions(
    start_date: date,
    end_date: date,
    base_url: str = BASE_URL_DEFAULT,
) -> list[Edition]:
    if end_date < start_date:
        raise ValueError("end_date must be >= start_date")

    session = _session()
    latest_url = f"{base_url}/apifront/portal/edicoes/ultimas_edicoes.json"
    latest_payload = _get_json(session, latest_url)

    raw_items = latest_payload.get("itens", [])
    editions: list[Edition] = []

    for item in raw_items:
        try:
            ed_date = _parse_date_ddmmyyyy(item["data"])
        except Exception:
            continue

        if not (start_date <= ed_date <= end_date):
            continue

        ed_id = int(item["id"])
        suplemento = int(item.get("suplemento") or 0)
        editions.append(
            Edition(
                id=ed_id,
                date_iso=ed_date.isoformat(),
                numero=item.get("numero"),
                suplemento=suplemento,
                suplemento_nome=item.get("suplemento_nome", "") or "",
                tipo_edicao_nome=item.get("tipo_edicao_nome", "") or "",
                pages=item.get("paginas"),
                pdf_url=f"{base_url}/portal/edicoes/download/{ed_id}",
                html_url=f"{base_url}/portal/visualizacoes/html/{ed_id}/#e:{ed_id}",
                jornal_url=f"{base_url}/portal/visualizacoes/jornal/{ed_id}/#e:{ed_id}",
                raw=item,
            )
        )

    # Fallback por data caso a lista de ultimas nao cubra toda a janela.
    check_date = start_date
    by_id = {e.id: e for e in editions}
    while check_date <= end_date:
        from_data_url = (
            f"{base_url}/apifront/portal/edicoes/edicoes_from_data/{check_date.isoformat()}.json"
        )
        try:
            payload = _get_json(session, from_data_url)
        except Exception:
            check_date += timedelta(days=1)
            continue

        for item in payload.get("itens", []):
            ed_id = int(item["id"])
            if ed_id in by_id:
                continue
            suplemento = int(item.get("suplemento") or 0)
            by_id[ed_id] = Edition(
                id=ed_id,
                date_iso=check_date.isoformat(),
                numero=item.get("numero"),
                suplemento=suplemento,
                suplemento_nome=item.get("suplemento_nome", "") or "",
                tipo_edicao_nome=item.get("tipo_edicao_nome", "") or "",
                pages=item.get("paginas"),
                pdf_url=f"{base_url}/portal/edicoes/download/{ed_id}",
                html_url=f"{base_url}/portal/visualizacoes/html/{ed_id}/#e:{ed_id}",
                jornal_url=f"{base_url}/portal/visualizacoes/jornal/{ed_id}/#e:{ed_id}",
                raw=item,
            )

        check_date += timedelta(days=1)

    result = sorted(by_id.values(), key=lambda x: (x.date_iso, x.id), reverse=True)
    return result
