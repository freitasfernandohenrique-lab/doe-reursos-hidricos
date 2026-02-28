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
        "A SANEAGO reforçou ações de saneamento e recursos hídricos. "
        "Também houve medidas para água e esgoto."
    )
    matches = find_matches(_edition(), text, source_type="pdf")
    assert matches
    groups = ",".join(m.keyword_group for m in matches)
    assert "saneago" in groups
    assert "saneamento" in groups
    assert "recursos hidricos" in groups
    assert "agua" in groups
    assert "esgoto" in groups


def test_dedupe_keeps_highest_score_per_context():
    text = (
        "SANEAGO e saneamento com valor de R$ 100.000,00 para ampliar rede de água e esgoto. "
        "SANEAGO e saneamento com valor de R$ 100.000,00 para ampliar rede de água e esgoto."
    )
    matches = find_matches(_edition(), text, source_type="pdf")
    assert len(matches) == 1
    score = matches[0].score
    assert score >= compute_score({"saneago", "saneamento", "agua", "esgoto"}, matches[0].context)
