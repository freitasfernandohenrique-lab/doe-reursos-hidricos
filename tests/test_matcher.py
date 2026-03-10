from src.matcher import compute_score, find_matches, find_secondary_municipal_alerts


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
    assert any(m.monitor_axis == "microrregioes_saneamento_basico" for m in matches)


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


def test_secondary_municipal_alert_captures_smae_without_axis_terms():
    text = (
        "A Superintendencia Municipal de Agua e Esgoto de Catalao informa manutencao programada "
        "na rede de abastecimento."
    )
    alerts = find_secondary_municipal_alerts(_edition(), text, source_type="html")
    assert alerts
    assert "superintendencia municipal de agua e esgoto" in alerts[0].keyword


def test_generic_hydric_axis_captures_non_microrregional_context():
    text = (
        "A SEMAD publica pedido de outorga para captacao de agua superficial "
        "e medidas de seguranca hidrica no municipio."
    )
    matches = find_matches(_edition(), text, source_type="html")
    assert matches
    assert all(m.monitor_axis == "recursos_hidricos_geral" for m in matches)
