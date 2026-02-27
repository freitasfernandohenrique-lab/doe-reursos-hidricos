from src.matcher import compute_score, find_matches


def _edition():
    return {
        "id": 999,
        "date_iso": "2026-02-27",
        "numero": 24728,
        "suplemento": 0,
        "pdf_url": "https://example.com/doc.pdf",
        "html_url": "https://example.com/doc.html",
    }


def test_find_matches_detects_keywords_with_accents():
    text = (
        "A SANEAGO publicou licitação para estação de tratamento de água e esgoto. "
        "Também houve outorga para captação de água."
    )
    matches = find_matches(_edition(), text, source_type="pdf")
    assert matches
    groups = ",".join(m.keyword_group for m in matches)
    assert "saneago" in groups
    assert "licitacao" in groups
    assert "outorga" in groups or "captacao" in groups


def test_dedupe_keeps_highest_score_per_context():
    text = (
        "Pregão da SANEAGO com valor de R$ 100.000,00 para contrato de manutenção. "
        "Pregão da SANEAGO com valor de R$ 100.000,00 para contrato de manutenção."
    )
    matches = find_matches(_edition(), text, source_type="pdf")
    assert len(matches) == 1
    score = matches[0].score
    assert score >= compute_score({"licitacao", "saneago", "contrato"}, matches[0].context)
