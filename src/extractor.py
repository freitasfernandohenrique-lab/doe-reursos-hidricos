"""Extração de texto de edições (HTML/Jornal com PDF opcional)."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Any

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@dataclass(slots=True)
class ExtractionResult:
    text: str
    source_type: str
    source_url: str
    pages: int | None
    warnings: list[str]


def _session(timeout: int = 45) -> requests.Session:
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
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.mount("http://", HTTPAdapter(max_retries=retries))
    session.headers.update({"User-Agent": "doego-monitor/1.0 (+github-actions)"})
    session.request_timeout = timeout  # type: ignore[attr-defined]
    return session


def _clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_pdf_bytes(content: bytes) -> tuple[str, int | None, list[str]]:
    warnings: list[str] = []
    try:
        import pdfplumber  # type: ignore
    except Exception as exc:
        warnings.append(f"pdfplumber não disponível: {exc}")
        pdfplumber = None

    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as exc:
        warnings.append(f"pypdf não disponível: {exc}")
        PdfReader = None

    if pdfplumber is not None:
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                pages = len(pdf.pages)
                parts = [p.extract_text() or "" for p in pdf.pages]
                text = _clean_text("\n".join(parts))
                if text:
                    return text, pages, warnings
                warnings.append("pdfplumber retornou texto vazio")
        except Exception as exc:
            warnings.append(f"pdfplumber falhou: {exc}")

    if PdfReader is not None:
        try:
            reader = PdfReader(io.BytesIO(content))
            parts = [p.extract_text() or "" for p in reader.pages]
            text = _clean_text("\n".join(parts))
            return text, len(reader.pages), warnings
        except Exception as exc:
            warnings.append(f"pypdf falhou: {exc}")

    return "", None, warnings


def _extract_html_text(content: str) -> str:
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    return _clean_text(text)


def _try_html(session: requests.Session, url: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    try:
        resp = session.get(url, timeout=getattr(session, "request_timeout", 45))
        if resp.ok and "text/html" in resp.headers.get("content-type", ""):
            text = _extract_html_text(resp.text)
            if len(text) > 1200:
                return text, warnings
            warnings.append("HTML com pouco conteúdo")
        else:
            warnings.append(f"HTML indisponível: status={resp.status_code}")
    except Exception as exc:
        warnings.append(f"Falha na coleta HTML: {exc}")
    return "", warnings


def extract_text_for_edition(
    edition: dict[str, Any],
    prefer_html: bool = True,
    allow_pdf_fallback: bool = False,
) -> ExtractionResult:
    session = _session()
    warnings: list[str] = []

    html_url = edition.get("html_url")
    jornal_url = edition.get("jornal_url")
    pdf_url = edition.get("pdf_url")

    if prefer_html and html_url:
        text, warns = _try_html(session, html_url)
        warnings.extend(warns)
        if text:
            return ExtractionResult(text=text, source_type="html", source_url=html_url, pages=None, warnings=warnings)

    if jornal_url:
        text, warns = _try_html(session, jornal_url)
        warnings.extend(warns)
        if text:
            return ExtractionResult(text=text, source_type="jornal", source_url=jornal_url, pages=None, warnings=warnings)

    if not allow_pdf_fallback:
        warnings.append("PDF fallback desativado")
        return ExtractionResult(text="", source_type="none", source_url=html_url or jornal_url or "", pages=None, warnings=warnings)

    if not pdf_url:
        return ExtractionResult(text="", source_type="none", source_url="", pages=None, warnings=warnings + ["Sem URL de PDF"])

    try:
        resp = session.get(pdf_url, timeout=getattr(session, "request_timeout", 45))
        resp.raise_for_status()
        text, pages, pdf_warnings = _extract_pdf_bytes(resp.content)
        warnings.extend(pdf_warnings)
        return ExtractionResult(text=text, source_type="pdf", source_url=pdf_url, pages=pages, warnings=warnings)
    except Exception as exc:
        warnings.append(f"Falha na coleta PDF: {exc}")
        return ExtractionResult(text="", source_type="pdf", source_url=pdf_url, pages=None, warnings=warnings)
