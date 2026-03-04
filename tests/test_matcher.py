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
        "Convocação de assembleia do colegiado microrregional para deliberar sobre "
        "saneamento e recursos hídricos, com medidas da SANEAGO para água e esgoto."
    )
    matches = find_matches(_edition(), text, source_type="pdf")
    assert matches
    groups = ",".join(m.keyword_group for m in matches)
    assert "convocacao" in groups
    assert "assembleia" in groups
    assert "microrregiao" in groups
    assert "saneago" in groups
    assert "saneamento" in groups
    assert "recursos hidricos" in groups
    assert "agua" in groups
    assert "esgoto" in groups


def test_dedupe_keeps_highest_score_per_context():
    text = (
        "Convocação de assembleia da microrregião para saneamento e recursos hídricos com valor de R$ 100.000,00. "
        "Convocação de assembleia da microrregião para saneamento e recursos hídricos com valor de R$ 100.000,00."
    )
    matches = find_matches(_edition(), text, source_type="pdf")
    assert len(matches) == 1
    score = matches[0].score
    assert score >= compute_score({"convocacao", "assembleia", "microrregiao", "saneamento", "recursos hidricos"}, matches[0].context)


def test_excludes_low_complexity_procurement_topics():
    text = (
        "Convocação de assembleia da microrregião para saneamento e recursos hídricos. "
        "Também informa pregão para material de expediente e serviços de limpeza."
    )
    matches = find_matches(_edition(), text, source_type="pdf")
    assert not matches
