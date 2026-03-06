"""Composição e envio de e-mail HTML."""

from __future__ import annotations

import html
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _tz_sp() -> timezone | ZoneInfo:
    try:
        return ZoneInfo("America/Sao_Paulo")
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=-3), name="BRT")


def _safe(v: Any) -> str:
    return html.escape(str(v or ""), quote=True)


def _list_links(items: list[dict[str, Any]], limit: int) -> str:
    rows = []
    for item in items[:limit]:
        reason = f"score {item['score']} | tema: {item['theme']}"
        rows.append(
            f"<li><a href='{_safe(item['link'])}'>{_safe(item['keyword'])}</a> - {_safe(reason)} - {_safe(item['orgao'])}</li>"
        )
    return "<ul>" + "".join(rows) + "</ul>" if rows else "<p>Sem destaques.</p>"


def _table_today(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<p>Sem ocorrências nas palavras-chave.</p>"
    trs = []
    for item in items:
        trs.append(
            "<tr>"
            f"<td>{_safe(item['orgao'])}</td>"
            f"<td>{_safe(item['theme'])}</td>"
            f"<td>{_safe(item['keyword'])}</td>"
            f"<td>{_safe(item['context'])}</td>"
            f"<td>{_safe(item.get('axis_analysis', ''))}</td>"
            f"<td>{_safe(item.get('correlated_not_prioritized', ''))}</td>"
            f"<td><a href='{_safe(item['link'])}'>link</a></td>"
            "</tr>"
        )
    return (
        "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%'>"
        "<thead><tr><th>Órgão</th><th>Tema</th><th>Palavra-chave</th><th>Trecho</th><th>Análise do eixo</th><th>Tema correlato não priorizado</th><th>Link</th></tr></thead>"
        f"<tbody>{''.join(trs)}</tbody></table>"
    )


def _table_secondary_alerts(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<p>Sem alertas secundários municipais.</p>"
    trs = []
    for item in items:
        trs.append(
            "<tr>"
            f"<td>{_safe(item.get('orgao', ''))}</td>"
            f"<td>{_safe(item.get('keyword', ''))}</td>"
            f"<td>{_safe(item.get('reason', ''))}</td>"
            f"<td>{_safe(item.get('context', ''))}</td>"
            f"<td><a href='{_safe(item.get('link', ''))}'>link</a></td>"
            "</tr>"
        )
    return (
        "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%'>"
        "<thead><tr><th>Órgão</th><th>Marcador</th><th>Motivo</th><th>Trecho</th><th>Link</th></tr></thead>"
        f"<tbody>{''.join(trs)}</tbody></table>"
    )


def _table_recent_7d(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<p>Sem ocorrências relevantes nos últimos 7 dias.</p>"
    trs = []
    for item in items:
        trs.append(
            "<tr>"
            f"<td>{_safe(item.get('date_iso', ''))}</td>"
            f"<td>{_safe(item.get('edition_numero', ''))}</td>"
            f"<td>{_safe(item.get('category', ''))}</td>"
            f"<td>{_safe(item.get('orgao', ''))}</td>"
            f"<td>{_safe(item.get('keyword', ''))}</td>"
            f"<td>{_safe(item.get('reason', ''))}</td>"
            f"<td>{_safe(item.get('context', ''))}</td>"
            f"<td><a href='{_safe(item.get('link', ''))}'>link</a></td>"
            "</tr>"
        )
    return (
        "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%'>"
        "<thead><tr><th>Data</th><th>Edição</th><th>Categoria</th><th>Órgão</th><th>Marcador</th><th>Motivo</th><th>Trecho</th><th>Link</th></tr></thead>"
        f"<tbody>{''.join(trs)}</tbody></table>"
    )


def build_email_html(
    report: dict[str, Any],
    run_meta: dict[str, Any],
    secondary_alerts_today: list[dict[str, Any]] | None = None,
    recent_items_7d: list[dict[str, Any]] | None = None,
) -> str:
    now_sp = datetime.now(_tz_sp()).strftime("%d/%m/%Y %H:%M:%S %Z")
    top_day = report.get("top_day", [])
    today_items = report.get("today_items", [])
    secondary_items = secondary_alerts_today or []
    recent_items = recent_items_7d or []
    warnings = run_meta.get("warnings", [])
    warnings_html = "<br/>".join(_safe(w) for w in warnings[:5]) if warnings else "Sem alertas técnicos."

    if not today_items:
        day_msg = "<p>Sem ocorrências nas palavras-chave. A coleta foi executada com sucesso.</p>"
    else:
        day_msg = ""

    html_body = f"""
    <html><body style='font-family:Arial,sans-serif'>
      <h2>[DOE-GO] Monitoramento Saneamento</h2>
      <p><b>Execução:</b> {_safe(now_sp)}<br/>
      <b>Fonte oficial:</b> <a href='https://diariooficial.abc.go.gov.br/'>DOE-GO</a><br/>
      <b>Janela analisada:</b> últimos {_safe(run_meta.get('scan_window_days', 1))} dias<br/>
      <b>Edições analisadas na janela:</b> {_safe(run_meta.get('editions_analyzed', 0))}<br/>
      <b>Edições de hoje:</b> {_safe(run_meta.get('editions_today', 0))}<br/>
      <b>Páginas analisadas:</b> {_safe(run_meta.get('pages_analyzed', 0))}<br/>
      <b>Alertas técnicos:</b> {warnings_html}</p>

      <h3>1) Resumo do dia</h3>
      {day_msg}
      {_list_links(top_day, limit=5)}

      <h3>2) Achados do dia (detalhado)</h3>
      {_table_today(today_items)}

      <h3>3) Alertas secundários municipais (fora do eixo principal)</h3>
      {_table_secondary_alerts(secondary_items)}

      <h3>4) Relatório dos últimos 7 dias</h3>
      <p><b>Ocorrências relevantes:</b> {_safe(run_meta.get('recent_items_count', 0))}<br/>
      <b>No eixo principal:</b> {_safe(run_meta.get('recent_primary_count', 0))}<br/>
      <b>Correlatas fora do eixo principal:</b> {_safe(run_meta.get('recent_secondary_count', 0))}</p>
      {_table_recent_7d(recent_items)}
    </body></html>
    """
    return html_body


def send_email_smtp(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_pass: str,
    email_from: str,
    email_to: list[str],
    subject: str,
    html_body: str,
) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = ", ".join(email_to)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(email_from, email_to, msg.as_string())
