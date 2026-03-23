from src.main import _merge_match_items, _merge_secondary_alerts
from src.matcher import MatchItem, SecondaryAlertItem


def test_merge_match_items_adds_pdf_only_occurrences_without_duplication():
    html_item = MatchItem(
        unique_id="html-1",
        date_iso="2026-03-23",
        edition_id=1,
        edition_numero=100,
        suplemento=0,
        keyword="saneamento",
        keyword_group="saneamento",
        context="Trecho encontrado no HTML.",
        score=2,
        theme="saneamento_recursos_hidricos",
        orgao="SEINFRA",
        link="https://example.com/1",
        source_type="html",
        monitor_axis="recursos_hidricos_geral",
        axis_analysis="HTML",
        correlated_not_prioritized="",
    )
    pdf_item = MatchItem(
        unique_id="pdf-1",
        date_iso="2026-03-23",
        edition_id=1,
        edition_numero=100,
        suplemento=0,
        keyword="convocação, assembleia, microrregião",
        keyword_group="assembleia,convocacao,microrregiao,saneamento",
        context="Trecho encontrado apenas no PDF.",
        score=5,
        theme="microregioes_recursos_hidricos",
        orgao="SEINFRA",
        link="https://example.com/1",
        source_type="pdf",
        monitor_axis="microrregioes_saneamento_basico",
        axis_analysis="PDF",
        correlated_not_prioritized="",
    )

    merged = _merge_match_items([html_item], [pdf_item])

    assert {item.unique_id for item in merged} == {"html-1", "pdf-1"}


def test_merge_secondary_alerts_deduplicates_by_unique_id():
    html_item = SecondaryAlertItem(
        unique_id="alert-1",
        date_iso="2026-03-23",
        edition_id=1,
        edition_numero=100,
        orgao="SMAE",
        keyword="smae",
        context="Trecho correlato.",
        reason="HTML",
        link="https://example.com/1",
        source_type="html",
    )
    pdf_item = SecondaryAlertItem(
        unique_id="alert-1",
        date_iso="2026-03-23",
        edition_id=1,
        edition_numero=100,
        orgao="SMAE",
        keyword="smae",
        context="Trecho correlato.",
        reason="PDF",
        link="https://example.com/1",
        source_type="pdf",
    )

    merged = _merge_secondary_alerts([html_item], [pdf_item])

    assert len(merged) == 1
    assert merged[0].source_type == "html"
