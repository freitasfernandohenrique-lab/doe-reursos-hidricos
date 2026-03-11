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


def _decorate_axis_items(report: dict[str, Any], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decorated: list[dict[str, Any]] = []
    for item in items:
        row = dict(item)
        row["monitor_axis_label"] = _axis_label(item.get("monitor_axis", ""), report)
        decorated.append(row)
    return decorated


def _summary_cards(report: dict[str, Any], run_meta: dict[str, Any]) -> str:
    cards = [
        ("Dia", report.get("counts", {}).get("items_today", 0)),
        ("5 dias", report.get("counts", {}).get("items_window", 0)),
        ("Edições", run_meta.get("editions_analyzed", 0)),
        ("Páginas", run_meta.get("pages_analyzed", 0)),
    ]
    html_cards = []
    for label, value in cards:
        html_cards.append(
            "<div style='flex:1;min-width:120px;background:#f4f7f4;border:1px solid #d7e1d6;border-radius:12px;padding:14px 16px'>"
            f"<div style='font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:#5b6b5d'>{_safe(label)}</div>"
            f"<div style='margin-top:6px;font-size:24px;font-weight:700;color:#17351f'>{_safe(value)}</div>"
            "</div>"
        )
    return "<div style='display:flex;gap:12px;flex-wrap:wrap;margin:18px 0 24px 0'>" + "".join(html_cards) + "</div>"


def _highlights(report: dict[str, Any]) -> str:
    blocks = []
    for axis in AXIS_ORDER:
        axis_data = report.get("sections", {}).get(axis, {})
        label = axis_data.get("label", axis)
        today_count = axis_data.get("today", {}).get("count", 0)
        window_count = axis_data.get("window", {}).get("count", 0)
        blocks.append(
            "<div style='padding:14px 16px;border:1px solid #e3e7e3;border-radius:12px;background:#fff'>"
            f"<div style='font-size:16px;font-weight:700;color:#17351f'>{_safe(label)}</div>"
            f"<div style='margin-top:6px;font-size:14px;color:#415343'>Hoje: <b>{_safe(today_count)}</b> | 5 dias: <b>{_safe(window_count)}</b></div>"
            "</div>"
        )
    return "<div style='display:grid;gap:10px;margin:0 0 24px 0'>" + "".join(blocks) + "</div>"


def _compact_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<p style='margin:0;color:#66756a'>Sem ocorrências relevantes.</p>"

    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f"<td style='padding:10px;border-top:1px solid #e8ece8;white-space:nowrap;vertical-align:top'>{_safe(item.get('date_iso', ''))}</td>"
            f"<td style='padding:10px;border-top:1px solid #e8ece8'>{_safe(item.get('context', ''))}</td>"
            f"<td style='padding:10px;border-top:1px solid #e8ece8;white-space:nowrap;vertical-align:top'><a href='{_safe(item.get('link', ''))}' style='color:#0b57d0;text-decoration:none'>abrir</a></td>"
            "</tr>"
        )

    return (
        "<table style='width:100%;border-collapse:collapse;font-size:14px;background:#fff;border:1px solid #e3e7e3;border-radius:12px;overflow:hidden'>"
        "<thead style='background:#f6f8f6'><tr>"
        "<th style='text-align:left;padding:10px;color:#4c5f4f'>Data</th>"
        "<th style='text-align:left;padding:10px;color:#4c5f4f'>Trecho</th>"
        "<th style='text-align:left;padding:10px;color:#4c5f4f'>Link</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _section(title: str, subtitle: str, table_html: str) -> str:
    return (
        "<section style='margin:0 0 28px 0'>"
        f"<h3 style='margin:0 0 6px 0;font-size:18px;color:#17351f'>{_safe(title)}</h3>"
        f"<p style='margin:0 0 12px 0;color:#5d6d60;font-size:14px'>{_safe(subtitle)}</p>"
        f"{table_html}"
        "</section>"
    )


def build_email_html(
    report: dict[str, Any],
    run_meta: dict[str, Any],
    secondary_alerts_today: list[dict[str, Any]] | None = None,
    recent_items_window: list[dict[str, Any]] | None = None,
) -> str:
    now_sp = datetime.now(_tz_sp()).strftime("%d/%m/%Y %H:%M")
    today_items = _decorate_axis_items(report, report.get("today_items", []))
    recent_items = recent_items_window or []
    secondary_items = secondary_alerts_today or []
    warnings = run_meta.get("warnings", [])
    warning_text = " | ".join(str(w) for w in warnings[:3]) if warnings else "Sem alertas técnicos."

    today_primary = [item for item in today_items if item.get("monitor_axis") == "microrregioes_saneamento_basico"]
    today_generic = [item for item in today_items if item.get("monitor_axis") == "recursos_hidricos_geral"]
    recent_primary = [item for item in recent_items if item.get("monitor_axis") == "microrregioes_saneamento_basico"]
    recent_generic = [item for item in recent_items if item.get("monitor_axis") == "recursos_hidricos_geral"]

    alerts_section = ""
    if secondary_items:
        alerts_section = _section(
            "Alertas correlatos",
            "Itens complementares de água e esgoto fora do eixo principal",
            _compact_table(secondary_items),
        )

    return f"""
    <html>
      <body style="margin:0;background:#eef3ee;padding:24px;font-family:Arial,sans-serif;color:#1f2a21">
        <div style="max-width:920px;margin:0 auto;background:#ffffff;border:1px solid #dce5dc;border-radius:20px;overflow:hidden">
          <div style="padding:28px 28px 18px 28px;background:linear-gradient(135deg,#17351f 0%,#2d5a38 100%);color:#ffffff">
            <div style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;opacity:.85">DOE-GO</div>
            <h1 style="margin:8px 0 8px 0;font-size:28px;line-height:1.1">Monitor diário de publicações</h1>
            <p style="margin:0;font-size:15px;line-height:1.5;max-width:720px">
              Objetivo: destacar só o que importa em microrregiões de saneamento básico e em recursos hídricos.
            </p>
          </div>

          <div style="padding:24px 28px 30px 28px">
            <p style="margin:0 0 8px 0;font-size:14px;color:#4b5c4d">
              Execução: <b>{_safe(now_sp)}</b> | Janela: <b>últimos {_safe(run_meta.get('scan_window_days', 5))} dias</b>
            </p>
            <p style="margin:0 0 20px 0;font-size:13px;color:#6a786b">
              {_safe(warning_text)}
            </p>

            {_summary_cards(report, run_meta)}
            {_highlights(report)}

            {_section(
                "Hoje | Microrregiões de saneamento básico",
                "Ocorrências do dia",
                _compact_table(today_primary),
            )}

            {_section(
                "Hoje | Recursos hídricos geral",
                "Ocorrências do dia",
                _compact_table(today_generic),
            )}

            {_section(
                "Últimos 5 dias | Microrregiões de saneamento básico",
                "Consolidação recente",
                _compact_table(recent_primary),
            )}

            {_section(
                "Últimos 5 dias | Recursos hídricos geral",
                "Consolidação recente",
                _compact_table(recent_generic),
            )}

            {alerts_section}
          </div>
        </div>
      </body>
    </html>
    """


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
