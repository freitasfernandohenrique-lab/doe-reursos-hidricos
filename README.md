# Monitor DOE-GO - Microrregiões e Recursos Hídricos

Robô em Python para monitorar o Diário Oficial do Estado de Goiás (DOE-GO), identificar publicações relevantes e enviar um e-mail diário com:

- análise específica do dia
- consolidação dos últimos 5 dias
- separação por dois eixos:
  - `microrregiões de saneamento básico`
  - `recursos hídricos geral`

A coleta usa a fonte oficial `https://diariooficial.abc.go.gov.br/` e endpoints públicos descobertos na própria página:

- `/apifront/portal/edicoes/ultimas_edicoes.json`
- `/apifront/portal/edicoes/edicoes_from_data/{YYYY-MM-DD}.json`

## Estrutura

- `src/fetcher.py`: descoberta de edições e links oficiais
- `src/extractor.py`: extração de texto HTML/Jornal (PDF opcional)
- `src/matcher.py`: keywords, classificação por eixo e deduplicação
- `src/analyzer.py`: agregações por eixo para o dia e para a janela recente
- `src/emailer.py`: HTML e envio SMTP
- `src/main.py`: orquestração, idempotência, outputs e modo demo
- `tests/test_matcher.py`: testes do matcher
- `.github/workflows/doego-email.yml`: execução diária com redundância
- `.github/workflows/doego-watchdog.yml`: fallback caso o envio principal não rode

## Requisitos

- Python 3.11+
- Dependências em `requirements.txt`

## Execução local

1. Instale as dependências:

```bash
pip install -r requirements.txt
```

2. Gere os artefatos sem enviar e-mail:

```bash
python -m src.main --no-send
```

3. Para envio SMTP, use variáveis de ambiente ou copie `config/monitor_diario_goias.env.example` para `config/monitor_diario_goias.env` e carregue os valores:

```bash
set EMAIL_FROM=seu@email.com
set EMAIL_TO=dest1@email.com,dest2@email.com
set SMTP_HOST=smtp.seuprovedor.com
set SMTP_PORT=587
set SMTP_USER=usuario
set SMTP_PASS=senha
python -m src.main
```

Para forçar reenvio no mesmo dia:

```bash
python -m src.main --force-send
```

Modo demo:

```bash
python -m src.main --demo
```

Self-test:

```bash
python -m src.main --self-test --no-send
```

## Saídas

Arquivos gerados em `outputs/`:

- `report.json`
- `matches_today.csv`
- `email.html`
- `sample_email.html`
- `self_test_email.html`

O `report.json` agora inclui:

- `report.sections.microrregioes_saneamento_basico`
- `report.sections.recursos_hidricos_geral`
- `recent_items_5d`

## GitHub Actions

Secrets esperados em `Settings > Secrets and variables > Actions`:

- `EMAIL_FROM`
- `EMAIL_TO`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASS`

O workflow principal:

- roda diariamente em `08:30` e `08:55` de `America/Sao_Paulo`
- mantém idempotência com `.state/sent_log.json`
- faz retry automático do monitor
- publica artefatos com HTML, JSON e log de envio

O watchdog:

- verifica se houve execução bem-sucedida no dia
- dispara `workflow_dispatch` do principal se necessário

## Deploy no Render

Há uma configuração pronta para Render em `render.yaml` e um guia passo a passo em `docs/deploy-render.md`.

No Render, este projeto deve ser criado como `Cron Job`.

Observação importante:

- no Render o armazenamento local é efêmero
- por isso a idempotência via `.state/sent_log.json` fica desabilitada por padrão nesse ambiente
- se você quiser idempotência persistente no Render, o ideal é mover esse estado para um datastore externo

## Janela e classificação

- A janela consolidada é de `5` dias, incluindo o dia corrente.
- O eixo `microrregiões de saneamento básico` prioriza convocações/assembleias do colegiado microrregional.
- O eixo `recursos hídricos geral` captura ocorrências amplas ligadas a saneamento, água, esgoto, SANEAGO, outorga e governança hídrica.
- Alertas municipais correlatos continuam destacados em seção própria no e-mail.

## Testes

```bash
pytest -q
```
