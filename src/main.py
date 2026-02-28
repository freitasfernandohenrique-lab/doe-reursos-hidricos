"""Orquestração principal do monitor DOE-GO."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.analyzer import analyze
from src.emailer import build_email_html, send_email_smtp
from src.extractor import extract_text_for_edition
from src.fetcher import discover_editions
from src.matcher import MatchItem, find_matches


def _tz_sp() -> timezone | ZoneInfo:
    try:
        return ZoneInfo("America/Sao_Paulo")
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=-3), name="BRT")


TZ = _tz_sp()


def _load_sent_log(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_sent_log(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _save_csv(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not items:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(items[0].keys()))
        writer.writeheader()
        writer.writerows(items)


def _today_sp() -> datetime:
    return datetime.now(TZ)


def _subject(today: datetime) -> str:
    return f"[DOE-GO] Monitoramento Saneamento — {today.strftime('%d/%m/%Y')}"


def _self_test_subject(now: datetime) -> str:
    return f"[DOE-GO][SELF-TEST] Monitoramento Saneamento — {now.strftime('%d/%m/%Y %H:%M:%S')}"


def _email_targets(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _demo_report(today_iso: str) -> tuple[dict[str, Any], dict[str, Any], str]:
    mock_items = [
        {
            "unique_id": "x1",
            "date_iso": today_iso,
            "edition_id": 7000,
            "edition_numero": 24700,
            "suplemento": 0,
            "keyword": "pregão, saneago",
            "keyword_group": "licitacao,saneago",
            "context": "A SANEAGO torna público o pregão eletrônico para contratação de serviços de manutenção da ETA... valor estimado de R$ 1.200.000,00 e prazo de 12 meses.",
            "score": 6,
            "theme": "licitacoes_contratos",
            "orgao": "SANEAGO",
            "link": "https://diariooficial.abc.go.gov.br/portal/edicoes/download/7000",
            "source_type": "pdf",
        },
        {
            "unique_id": "x2",
            "date_iso": today_iso,
            "edition_id": 7001,
            "edition_numero": 24701,
            "suplemento": 1,
            "keyword": "outorga, captação",
            "keyword_group": "outorga,captacao,recursos hidricos",
            "context": "Publica-se pedido de outorga para captação de água superficial no município...",
            "score": 4,
            "theme": "outorgas_recursos_hidricos",
            "orgao": "SEMAD",
            "link": "https://diariooficial.abc.go.gov.br/portal/edicoes/download/7001",
            "source_type": "pdf",
        },
    ]
    typed = [MatchItem(**i) for i in mock_items]
    report = analyze(typed, today_iso=today_iso)
    run_meta = {
        "editions_analyzed": 2,
        "pages_analyzed": 120,
        "duration_seconds": 1,
        "warnings": ["Dados simulados para demonstração"],
    }
    html = build_email_html(report, run_meta)
    return report, run_meta, html


def _self_test_report(today_iso: str) -> tuple[dict[str, Any], dict[str, Any], str]:
    mock_item = {
        "unique_id": "self-test-1",
        "date_iso": today_iso,
        "edition_id": 99999,
        "edition_numero": 99999,
        "suplemento": 0,
        "keyword": "self-test, saneago, pregão",
        "keyword_group": "self-test,licitacao,saneago",
        "context": "SELF-TEST: ocorrência simulada para validar pipeline completo de análise e envio de e-mail.",
        "score": 9,
        "theme": "licitacoes_contratos",
        "orgao": "SELF-TEST",
        "link": "https://diariooficial.abc.go.gov.br/",
        "source_type": "simulated",
    }
    typed = [MatchItem(**mock_item)]
    report = analyze(typed, today_iso=today_iso)
    run_meta = {
        "editions_analyzed": 1,
        "pages_analyzed": 1,
        "duration_seconds": 1,
        "warnings": ["Execução de self-test (dados simulados, sem chamada ao DOE)"],
    }
    html = build_email_html(report, run_meta)
    return report, run_meta, html


def _send_if_configured(today: datetime, html_body: str, send_email: bool, subject: str) -> int:
    if not send_email:
        print("Execução sem envio de e-mail (--no-send).")
        return 0

    email_from = os.getenv("EMAIL_FROM", "")
    email_to_raw = os.getenv("EMAIL_TO", "")
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")

    required = [email_from, email_to_raw, smtp_host, smtp_user, smtp_pass]
    if not all(required):
        print("Credenciais SMTP/EMAIL ausentes. Arquivos gerados sem envio.")
        return 0

    recipients = _email_targets(email_to_raw)
    if not recipients:
        print("EMAIL_TO vazio após parsing.")
        return 0

    try:
        send_email_smtp(
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_user=smtp_user,
            smtp_pass=smtp_pass,
            email_from=email_from,
            email_to=recipients,
            subject=subject,
            html_body=html_body,
        )
        print(f"E-mail enviado com sucesso para {len(recipients)} destinatário(s).")
        return 0
    except Exception as exc:
        print(f"Falha no envio SMTP: {exc}", file=sys.stderr)
        return 3


def run(demo: bool = False, self_test: bool = False, send_email: bool = True) -> int:
    started = time.time()
    today = _today_sp()
    today_iso = today.date().isoformat()

    out_dir = Path(os.getenv("OUTPUT_DIR", "outputs"))
    state_file = Path(os.getenv("SENT_LOG_PATH", ".state/sent_log.json"))

    if demo:
        report, run_meta, html_body = _demo_report(today_iso)
        _save_json(out_dir / "report_demo.json", report)
        (out_dir / "sample_email.html").write_text(html_body, encoding="utf-8")
        print("Modo demo finalizado. Arquivos gerados em outputs/.")
        return 0

    if self_test:
        report, run_meta, html_body = _self_test_report(today_iso)
        _save_json(out_dir / "report_self_test.json", report)
        (out_dir / "self_test_email.html").write_text(html_body, encoding="utf-8")
        code = _send_if_configured(
            today=today,
            html_body=html_body,
            send_email=send_email,
            subject=_self_test_subject(today),
        )
        if code == 0:
            print("Self-test finalizado.")
        return code

    sent_log = _load_sent_log(state_file)
    if sent_log.get(today_iso, {}).get("sent"):
        print(f"E-mail já enviado em {today_iso}. Encerrando de forma idempotente.")
        return 0

    start_date = today.date() - timedelta(days=29)
    end_date = today.date()

    warnings: list[str] = []
    try:
        editions = discover_editions(start_date=start_date, end_date=end_date)
    except Exception as exc:
        print(f"Falha na descoberta de edições: {exc}", file=sys.stderr)
        return 2

    matches: list[MatchItem] = []
    pages_analyzed = 0
    allow_pdf_fallback = _env_bool("ENABLE_PDF_FALLBACK", default=False)
    for edition in editions:
        extracted = extract_text_for_edition(
            edition.to_dict(),
            prefer_html=True,
            allow_pdf_fallback=allow_pdf_fallback,
        )
        pages_analyzed += int(extracted.pages or 0)
        warnings.extend(extracted.warnings)
        found = find_matches(edition.to_dict(), extracted.text, source_type=extracted.source_type)
        matches.extend(found)

    report = analyze(matches, today_iso=today_iso)

    duration = round(time.time() - started, 2)
    run_meta = {
        "editions_analyzed": len(editions),
        "pages_analyzed": pages_analyzed,
        "duration_seconds": duration,
        "warnings": sorted(set(warnings))[:30],
    }

    report_full = {"report": report, "run_meta": run_meta, "editions": [e.to_dict() for e in editions]}
    today_items = report.get("today_items", [])

    _save_json(out_dir / "report.json", report_full)
    _save_csv(out_dir / "matches_today.csv", today_items)
    _save_csv(out_dir / "matches_30d.csv", [m.to_dict() for m in matches])

    html_body = build_email_html(report, run_meta)
    (out_dir / "email.html").write_text(html_body, encoding="utf-8")

    code = _send_if_configured(today=today, html_body=html_body, send_email=send_email, subject=_subject(today))
    if code != 0:
        return code

    if send_email:
        sent_log[today_iso] = {
            "sent": True,
            "sent_at": _today_sp().isoformat(),
            "items_today": len(today_items),
            "editions_analyzed": len(editions),
        }
        _save_sent_log(state_file, sent_log)
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor DOE-GO saneamento")
    parser.add_argument("--demo", action="store_true", help="Gera e-mail de exemplo com dados simulados")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Gera e-mail de teste com 1 ocorrência simulada (sem chamar DOE).",
    )
    parser.add_argument("--no-send", action="store_true", help="Processa dados sem enviar e-mail")
    args = parser.parse_args()
    if args.demo and args.self_test:
        parser.error("Use apenas um modo especial por vez: --demo ou --self-test.")
    return args


if __name__ == "__main__":
    args = _parse_args()
    code = run(demo=args.demo, self_test=args.self_test, send_email=not args.no_send)
    raise SystemExit(code)
