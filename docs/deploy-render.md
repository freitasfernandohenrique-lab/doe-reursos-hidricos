# Deploy no Render

Este projeto deve ser publicado no Render como um `Cron Job`, não como `Web Service`.

O motivo é simples: o código não expõe uma aplicação HTTP. Ele executa uma rotina diária que consulta o DOE-GO, gera arquivos em `outputs/` e envia um e-mail via SMTP.

## O que foi preparado no repositório

- `render.yaml`: blueprint pronto para criar o serviço no Render
- `.python-version`: fixa a major version do Python para manter compatibilidade
- `pytest.ini`: garante que `pytest` encontre `src` corretamente
- `src/main.py`: desabilita a idempotência por arquivo local por padrão quando roda no Render, porque o filesystem do serviço é efêmero

## Como fazer o deploy

1. Suba esta branch para o GitHub/GitLab/Bitbucket.
2. No Render, abra `Blueprints`.
3. Clique em `New Blueprint Instance`.
4. Conecte o repositório e selecione a branch desejada.
5. O Render vai detectar o arquivo `render.yaml` e propor a criação do serviço `doego-monitor-saneamento`.
6. Preencha os secrets solicitados:
   - `EMAIL_FROM`
   - `EMAIL_TO`
   - `SMTP_HOST`
   - `SMTP_USER`
   - `SMTP_PASS`
7. Revise o plano e confirme a criação.

## Configuração incluída

O `render.yaml` cria um `Cron Job` Python com:

- `buildCommand`: `pip install -r requirements.txt`
- `startCommand`: `python -m src.main`
- `schedule`: `30 11 * * *`

Esse cron está em UTC. Na prática, `30 11 * * *` corresponde a `08:30` em `America/Sao_Paulo`.

## Variáveis de ambiente

Estas variáveis já ficam previstas no blueprint:

- `PYTHON_VERSION=3.11.11`
- `ENABLE_PDF_FALLBACK=true`
- `ENABLE_SENT_LOG=false`
- `SMTP_PORT=587`

E estas devem ser preenchidas no painel do Render:

- `EMAIL_FROM`
- `EMAIL_TO`
- `SMTP_HOST`
- `SMTP_USER`
- `SMTP_PASS`

## Sobre a idempotência no Render

Localmente e no GitHub Actions, o projeto usa `.state/sent_log.json` para evitar reenvio no mesmo dia.

No Render, isso não é confiável por padrão porque o armazenamento local do serviço não deve ser tratado como persistente entre execuções. Por isso o código agora desabilita automaticamente esse controle quando detecta `RENDER=true`.

Impacto prático:

- a execução agendada diária funciona normalmente
- se você disparar o job manualmente no mesmo dia, ele pode reenviar o e-mail

Se você quiser manter idempotência real no Render, o próximo passo recomendado é mover esse estado para um datastore externo, como Render Key Value ou Postgres.

## Como validar após o deploy

1. Abra o serviço no Render.
2. Use `Manual Run` para executar uma vez.
3. Verifique os logs da execução.
4. Confirme que:
   - a coleta das edições foi concluída
   - o HTML do e-mail foi gerado
   - o SMTP autenticou com sucesso
   - o e-mail chegou aos destinatários

## Comandos úteis locais

Instalar dependências:

```bash
pip install -r requirements.txt
```

Rodar sem envio:

```bash
python -m src.main --no-send
```

Rodar self-test sem acessar DOE:

```bash
python -m src.main --self-test --no-send
```

Rodar testes:

```bash
pytest -q
```

## Observações

- `outputs/` continua útil para debug local, mas não deve ser tratado como armazenamento permanente no Render.
- Se o provedor SMTP exigir SSL implícito em vez de STARTTLS, será preciso ajustar `src/emailer.py`.
- Se você preferir manter também o GitHub Actions, ele pode coexistir com o Render, mas os dois não devem enviar para a mesma lista ao mesmo tempo.
