"""Composição e envio de e-mail HTML."""

from __future__ import annotations

import html
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


AXIS_ORDER = [
    "microrregioes_saneamento_basico",
    "recursos_hidricos_geral",
]


def _tz_sp() -> timezone | ZoneInfo:
    try:
        return ZoneInfo("America/Sao_Paulo")
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=-3), name="BRT")


def _safe(v: Any) -> str:
    return html.escape(str(v or ""), quote=True)


def _axis_label(axis: str, report: dict[str, Any]) -> str:
    return report.get("sections", {}).get(axis, {}).get("label", axis)


def _list_axis_items(items: list[dict[str, Any]], limit: int) -> str:
    rows = []
    for item in items[:limit]:
        reason = item.get("axis_analysis") or f"score {item.get('score', 0)} | tema: {item.get('theme', '')}"
        rows.append(
            f"<li><a href='{_safe(item.get('link', ''))}'>{_safe(item.get('keyword', ''))}</a> - {_safe(reason)} - {_safe(item.get('orgao', ''))}</li>"
        )
    return "<ul>" + "".join(rows) + "</ul>" if rows else "<p>Sem destaques.</p>"


def _table_items(items: list[dict[str, Any]], include_axis: bool = False) -> str:
    if not items:
        return "<p>Sem ocorrências.</p>"

    headers = ["Órgão", "Tema", "Palavra-chave", "Trecho", "Análise", "Link"]
    if include_axis:
        headers.insert(0, "Eixo")

    trs = []
    for item in items:
        cells = [
            f"<td>{_safe(item.get('orgao', ''))}</td>",
            f"<td>{_safe(item.get('theme', ''))}</td>",
            f"<td>{_safe(item.get('keyword', ''))}</td>",
            f"<td>{_safe(item.get('context', ''))}</td>",
            f"<td>{_safe(item.get('axis_analysis', ''))}</td>",
            f"<td><a href='{_safe(item.get('link', ''))}'>link</a></td>",
        ]
        if include_axis:
            cells.insert(0, f"<td>{_safe(item.get('monitor_axis_label', ''))}</td>")
        trs.append("<tr>" + "".join(cells) + "</tr>")

    header_html = "".join(f"<th>{_safe(header)}</th>" for header in headers)
    return (
        "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%'>"
        f"<thead><tr>{header_html}</tr></thead>"
        f"<tbody>{''.join(trs)}</tbody></table>"
    )


def _table_secondary_alerts(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<p>Sem alertas correlatos.</p>"
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


def _table_recent(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<p>Sem ocorrências relevantes.</p>"
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


def _decorate_axis_items(report: dict[str, Any], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decorated: list[dict[str, Any]] = []
    for item in items:
        new_item = dict(item)
        new_item["monitor_axis_label"] = _axis_label(item.get("monitor_axis", ""), report)
        decorated.append(new_item)
    return decorated


def build_email_html(
    report: dict[str, Any],
    run_meta: dict[str, Any],
    secondary_alerts_today: list[dict[str, Any]] | None = None,
    recent_items_window: list[dict[str, Any]] | None = None,
) -> str:
    now_sp = datetime.now(_tz_sp()).strftime("%d/%m/%Y %H:%M:%S %Z")
    warnings = run_meta.get("warnings", [])
    warnings_html = "<br/>".join(_safe(w) for w in warnings[:5]) if warnings else "Sem alertas técnicos."
    today_items = _decorate_axis_items(report, report.get("today_items", []))
    recent_items = recent_items_window or []
    secondary_items = secondary_alerts_today or []

    sections_html = []
    for axis in AXIS_ORDER:
        axis_data = report.get("sections", {}).get(axis, {})
        label = axis_data.get("label", axis)
        today_data = axis_data.get("today", {})
        window_data = axis_data.get("window", {})
        today_top = _decorate_axis_items(report, today_data.get("top_items", []))
        window_top = _decorate_axis_items(report, window_data.get("top_items", []))
        sections_html.append(
            f"""
            <h3>{_safe(label)}</h3>
            <p><b>Achados do dia:</b> {_safe(today_data.get('count', 0))}<br/>
            <b>Ocorrências na janela:</b> {_safe(window_data.get('count', 0))}</p>
            <p><b>Destaques do dia</b></p>
            {_list_axis_items(today_top, limit=5)}
            <p><b>Destaques dos últimos {_safe(run_meta.get('scan_window_days', 5))} dias</b></p>
            {_list_axis_items(window_top, limit=8)}
            """
        )

    html_body = f"""
    <html><body style='font-family:Arial,sans-serif'>
      <h2>[DOE-GO] Monitoramento Diário</h2>
      <p><b>Execução:</b> {_safe(now_sp)}<br/>
      <b>Fonte oficial:</b> <a href='https://diariooficial.abc.go.gov.br/'>DOE-GO</a><br/>
      <b>Janela analisada:</b> últimos {_safe(run_meta.get('scan_window_days', 5))} dias<br/>
      <b>Edições analisadas na janela:</b> {_safe(run_meta.get('editions_analyzed', 0))}<br/>
      <b>Edições do dia:</b> {_safe(run_meta.get('editions_today', 0))}<br/>
      <b>Páginas analisadas:</b> {_safe(run_meta.get('pages_analyzed', 0))}<br/>
      <b>Alertas técnicos:</b> {warnings_html}</p>

      <h3>1) Análise específica do dia</h3>
      <p><b>Total de ocorrências do dia:</b> {_safe(report.get('counts', {}).get('items_today', 0))}</p>
      {''.join(sections_html)}

      <h3>2) Achados do dia em detalhe</h3>
      {_table_items(today_items, include_axis=True)}

      <h3>3) Alertas correlatos municipais</h3>
      {_table_secondary_alerts(secondary_items)}

      <h3>4) Análise consolidada dos últimos {_safe(run_meta.get('scan_window_days', 5))} dias</h3>
      <p><b>Ocorrências relevantes:</b> {_safe(run_meta.get('recent_items_count', 0))}<br/>
      <b>No eixo microrregiões:</b> {_safe(report.get('sections', {}).get('microrregioes_saneamento_basico', {}).get('window', {}).get('count', 0))}<br/>
      <b>No eixo recursos hídricos geral:</b> {_safe(report.get('sections', {}).get('recursos_hidricos_geral', {}).get('window', {}).get('count', 0))}<br/>
      <b>Alertas correlatos adicionais:</b> {_safe(run_meta.get('recent_secondary_count', 0))}</p>
      {_table_recent(recent_items)}
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
