# Monitor DOE-GO - Saneamento

Robô em Python para monitorar o Diário Oficial do Estado de Goiás (DOE-GO), identificar publicações relacionadas a saneamento e enviar e-mail diário com:

- análise do dia (edição mais recente/data corrente)
- análise consolidada dos últimos 30 dias (janela móvel)

A coleta usa a fonte oficial `https://diariooficial.abc.go.gov.br/` e endpoints públicos descobertos na própria página:

- `/apifront/portal/edicoes/ultimas_edicoes.json`
- `/apifront/portal/edicoes/edicoes_from_data/{YYYY-MM-DD}.json`

## Estrutura

- `src/fetcher.py`: descoberta de edições e links oficiais
- `src/extractor.py`: extração de texto HTML/Jornal (PDF opcional)
- `src/matcher.py`: keywords, contexto, dedupe, score
- `src/analyzer.py`: métricas e tendências
- `src/emailer.py`: HTML e envio SMTP
- `src/main.py`: orquestração, idempotência, outputs e modo demo
- `tests/test_matcher.py`: testes de matcher/dedupe
- `.github/workflows/doego-email.yml`: execução diária no GitHub Actions

## Requisitos

- Python 3.11+
- Dependências em `requirements.txt`

## Execução local

1. Instalar dependências:

```bash
pip install -r requirements.txt
```

2. Rodar processamento sem enviar e-mail:

```bash
python -m src.main --no-send
```

3. Rodar com envio SMTP (defina variáveis de ambiente):

```bash
set EMAIL_FROM=seu@email.com
set EMAIL_TO=dest1@email.com,dest2@email.com
set SMTP_HOST=smtp.seuprovedor.com
set SMTP_PORT=587
set SMTP_USER=usuario
set SMTP_PASS=senha
python -m src.main
```

Para forçar reenvio no mesmo dia (ignorando idempotência):

```bash
python -m src.main --force-send
```

4. Gerar e-mail de exemplo com dados simulados (sem chamar DOE):

```bash
python -m src.main --demo
```

5. Rodar self-test ponta-a-ponta com 1 ocorrência fake (sem chamar DOE):

```bash
python -m src.main --self-test
```

Para validar sem enviar e-mail:

```bash
python -m src.main --self-test --no-send
```

Arquivos gerados em `outputs/`:

- `report.json`
- `matches_today.csv`
- `matches_30d.csv`
- `email.html`
- `sample_email.html` (modo demo)
- `self_test_email.html` (modo self-test)

## Configuração de secrets no GitHub

No repositório, configure em `Settings > Secrets and variables > Actions`:

- `EMAIL_FROM`
- `EMAIL_TO` (um ou vários separados por vírgula)
- `SMTP_HOST`
- `SMTP_PORT` (ex.: `587`)
- `SMTP_USER`
- `SMTP_PASS`

## Workflow diário

Arquivo: `.github/workflows/doego-email.yml`

- Runner: `ubuntu-latest`
- Cron: `30 11 * * *` (UTC, equivalente a 08:30 em America/Sao_Paulo)
- Etapas:
  - checkout
  - setup Python
  - restore cache de `.state/sent_log.json`
  - install deps
  - executar `python -m src.main`
  - gerar demo `python -m src.main --demo`
  - upload artifacts (`outputs/`, `.state/sent_log.json`)
  - save cache do sent log

No `Run workflow` manual, você pode marcar `force_send=true` para reenviar no mesmo dia.

## Idempotência

O envio é controlado por `.state/sent_log.json` (chave por data local `America/Sao_Paulo`).

Se o workflow rodar duas vezes no mesmo dia e `sent=true`, o script encerra sem reenviar e-mail.

No GitHub Actions, o arquivo é persistido entre execuções via cache (`actions/cache`).

## Palavras-chave e temas

As keywords estão em `src/matcher.py` no dicionário `KEYWORD_ALIASES`.

Para adicionar/remover termos:

1. edite `KEYWORD_ALIASES`
2. ajuste `THEME_RULES` se quiser mudar o agrupamento de temas

Busca é case-insensitive e normalizada para acentos.

## Ranking de relevância

Implementado conforme regra:

- `+3`: licitação/pregão/concorrência/dispensa/inexigibilidade
- `+2`: SANEAGO
- `+2`: outorga/captação/recursos hídricos
- `+1`: valores/quantias ou prazos (regex)
- `+1`: contrato/aditivo

Ordenação: score desc, depois data/edição.

## Extração leve (sem PDF por padrão)

Por padrão, o robô usa apenas fontes HTML (`visualizacoes/html` e `visualizacoes/jornal`), que são mais leves e rápidas.

Para habilitar fallback em PDF quando necessário, defina:

```bash
set ENABLE_PDF_FALLBACK=true
```

E instale dependências opcionais de PDF:

```bash
pip install pdfplumber pypdf
```

No GitHub Actions, a variável já está configurada como `false` para manter execução mais leve.

## Observabilidade e resiliência

- Logs no console do workflow
- Artifacts com JSON/CSV/HTML
- Retries e timeouts para rede
- Fallback opcional de extração HTML/Jornal -> PDF
- Registro de alertas técnicos no rodapé do e-mail

## Testes

```bash
pytest -q
```
