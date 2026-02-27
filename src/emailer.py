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
            f"<td><a href='{_safe(item['link'])}'>link</a></td>"
            "</tr>"
        )
    return (
        "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%'>"
        "<thead><tr><th>Órgão</th><th>Tema</th><th>Palavra-chave</th><th>Trecho</th><th>Link</th></tr></thead>"
        f"<tbody>{''.join(trs)}</tbody></table>"
    )


def build_email_html(report: dict[str, Any], run_meta: dict[str, Any]) -> str:
    now_sp = datetime.now(_tz_sp()).strftime("%d/%m/%Y %H:%M:%S %Z")
    top_day = report.get("top_day", [])
    top_10d = report.get("top_10d", [])
    today_items = report.get("today_items", [])
    keywords = report.get("keywords_10d", {})
    themes = report.get("themes_10d", {})
    counts = report.get("counts", {})

    kw_rows = "".join(f"<li>{_safe(k)}: {_safe(v)}</li>" for k, v in keywords.items())
    th_rows = "".join(f"<li>{_safe(k)}: {_safe(v)}</li>" for k, v in themes.items())

    if not today_items:
        day_msg = "<p>Sem ocorrências nas palavras-chave. A coleta foi executada com sucesso.</p>"
    else:
        day_msg = ""

    html_body = f"""
    <html><body style='font-family:Arial,sans-serif'>
      <h2>[DOE-GO] Monitoramento Saneamento</h2>
      <p><b>Execução:</b> {_safe(now_sp)}<br/>
      <b>Fonte oficial:</b> <a href='https://diariooficial.abc.go.gov.br/'>DOE-GO</a></p>

      <h3>1) Resumo do dia</h3>
      {day_msg}
      {_list_links(top_day, limit=5)}

      <h3>2) Achados do dia (detalhado)</h3>
      {_table_today(today_items)}

      <h3>3) Últimos 10 dias</h3>
      <p><b>Total de itens (10d):</b> {_safe(counts.get('items_10d', 0))}<br/>
         <b>Novos:</b> {_safe(counts.get('new_items', 0))} | <b>Recorrentes:</b> {_safe(counts.get('recurring_items', 0))}</p>
      <p><b>Contagem por palavra-chave</b></p><ul>{kw_rows or '<li>Sem dados</li>'}</ul>
      <p><b>Contagem por tema</b></p><ul>{th_rows or '<li>Sem dados</li>'}</ul>
      <p><b>Top 10 itens relevantes</b></p>
      {_list_links(top_10d, limit=10)}

      <h3>4) Rodapé técnico</h3>
      <p>
        Edições analisadas: {_safe(run_meta.get('editions_analyzed', 0))}<br/>
        Páginas analisadas (aprox.): {_safe(run_meta.get('pages_analyzed', 0))}<br/>
        Duração: {_safe(run_meta.get('duration_seconds', 0))} s<br/>
        Erros/alertas: {_safe('; '.join(run_meta.get('warnings', [])) or 'Nenhum')}
      </p>
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
