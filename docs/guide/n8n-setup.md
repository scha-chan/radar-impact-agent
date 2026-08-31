# Guia — Automação low-code (n8n)

> Detalhamento da seção [Automação low-code (n8n)](../../README.md#automação-low-code-n8n) do README.
> O README traz o resumo do fluxo e as instruções mínimas de reprodução; este guia é o passo a passo completo com resolução de problemas.

Fluxo (seção 17 do PRD, card 29): Issue com o label `analise-impacto` → webhook do GitHub → **n8n** → `POST /analyze` na aplicação → resultado distribuído como card no **Discord**, com o resumo do parecer e um link para o painel de aprovação. Toda a lógica de análise, classificação e decisão de autonomia mora na aplicação — o n8n só encaminha o gatilho e distribui o resultado; nenhuma regra de negócio vive no workflow.

Workflow exportado: [`docs/lowcode/workflow-n8n.json`](../lowcode/workflow-n8n.json).

**Segundo caminho até o Discord (card 52).** Uma análise submetida pela página (card 30) não passa por este workflow — o gatilho dela é `POST /analyze` direto, sem n8n. Para o card do Discord sair também nesse caso (e depois de uma aprovação no painel), o backend chama, ao fim de toda análise que publicou parecer, um webhook dedicado do n8n com o **texto completo do parecer** (o mesmo de `audit/dry_run/`). Workflow: [`docs/lowcode/workflow-n8n-parecer.json`](../lowcode/workflow-n8n-parecer.json) — `Webhook (radar-parecer)` → `HTTP Request` para o Discord, sem `IF` e sem chamada de volta a `/analyze` (evita loop). Configuração no passo 8.

## Configurando o n8n passo a passo

1. **Suba os serviços** (`docker-compose.yml` já traz `radar` + `n8n`):

   ```bash
   docker compose up -d
   ```

   API em `http://localhost:8000`, n8n em `http://localhost:5678`. O Ollama continua no host (não é containerizado).

2. **Crie a conta local de admin** na primeira vez que abrir `http://localhost:5678` — é o *owner account* do n8n, gravado no volume `n8n-data`. Local, não é cadastro no n8n.io cloud.

3. **Importe o workflow.** No n8n atual a importação não fica na tela inicial: clique em **Criar workflow**, e já dentro do editor use o menu **⋮** (canto superior direito) → **Importar de arquivo** → [`docs/lowcode/workflow-n8n.json`](../lowcode/workflow-n8n.json). Alternativa: abrir o JSON num editor, copiar tudo e colar (`Ctrl+V`) no canvas em branco.

4. **Variáveis de ambiente.** O `docker-compose.yml` já injeta no container do n8n, com alguns valores **fixos de propósito** (não interpolados do `.env`, porque `localhost` dentro de um container é o próprio container):

   | Variável | Valor no container | Porquê |
   |---|---|---|
   | `RADAR_API_URL` | `http://radar:8000` | comunicação container-a-container usa o nome do serviço; `localhost` seria o próprio n8n |
   | `RADAR_APPROVAL_URL` | `http://localhost:8000` (do `.env`) | vira link clicável no card do Discord, aberto no navegador do host |
   | `DISCORD_WEBHOOK_URL` | do seu `.env` | crie um webhook em **Configurações do Canal → Integrações → Webhooks** no seu servidor Discord e cole no `.env`. **Nunca** commite essa URL |
   | `N8N_BLOCK_ENV_ACCESS_IN_NODE` | `false` | o n8n recente bloqueia `{{$env.*}}` nas expressões por padrão (`access to env vars denied`); o workflow usa `$env` para as três URLs acima |
   | `OLLAMA_BASE_URL` (serviço `radar`) | `http://host.docker.internal:11434` | o Ollama roda no host; dentro do container `localhost` não o alcança |

   Depois de mexer no `.env`, recrie os containers: `docker compose up -d --force-recreate`.

5. **Node de notificação do Discord.** O node nativo **Discord** (v2) do n8n tem incompatibilidade na importação do workflow (parâmetro órfão `sendLegacy: undefined`, falha de TLS ao enviar). Substitua por um **HTTP Request** apontando direto para o webhook — o webhook do Discord é só um endpoint HTTP, e isso reforça a divisão de responsabilidade da seção 17 (o n8n só encaminha):

   - **Method** `POST` · **URL** `{{ $env.DISCORD_WEBHOOK_URL }}`
   - **Send Body** on · **Body Content Type** `JSON` · **Specify Body** `Using JSON`
   - **JSON** (modo expressão):

     ```
     ={{ { "content": "**Novo parecer RADAR — Issue #" + $('GitHub Webhook').item.json.body.issue.number + "**\n\nNível de risco: **" + ($json.risk_assessed ? $json.risk_level : "não avaliado") + "**\nConfiança: " + $json.confidence + "\nRevisão humana necessária: " + $json.human_review_required + "\n\n🔗 Painel: " + $env.RADAR_APPROVAL_URL + "/approvals/" + $json.session_id } }}
     ```

   - Sucesso = HTTP `204`. Religue `POST /analyze` → `HTTP Request`.

6. **Webhook do GitHub.** No node **GitHub Webhook**, copie a "Production URL" e cadastre em **Settings → Webhooks → Add webhook** do repositório: evento `Issues`, `Content type: application/json`. Para testar sem o GitHub, dispare um `curl` com o payload no formato do evento `issues` — **objeto único** (não array) e, a partir do card 52, `label` como **string** (não mais objeto `{name}`):

   ```bash
   curl -X POST http://localhost:5678/webhook-test/radar-analise-impacto \
     -H 'Content-Type: application/json' \
     -d '{"action":"labeled","label":"analise-impacto","issue":{"number":42,"body":"Adicionar paginação e ordenação no painel de aprovações."}}'
   ```

   A URL `/webhook-test/...` só responde enquanto o n8n está em **Listen for test event**; a de produção é `/webhook/...` (sem `-test`), com o workflow **Active**.

7. **Ative o workflow** (toggle **Active**) e crie uma Issue com o label `analise-impacto`.

8. **Notificação do parecer ao fim da análise (card 52).** Importe [`docs/lowcode/workflow-n8n-parecer.json`](../lowcode/workflow-n8n-parecer.json) como um **segundo workflow**. Ele tem só `Webhook (radar-parecer)` → `HTTP Request` (Discord); o `HTTP Request` já vem com `URL = {{$env.DISCORD_WEBHOOK_URL}}` e o corpo montando o card a partir de `{{$json.body.parecer.slice(0, 1800)}}` (o `.slice` respeita o limite de 2000 chars do Discord). **Ative** o workflow e use a URL de produção (`/webhook/radar-parecer`).

   No serviço `radar` (não no n8n), configure no `.env` e recrie os containers:

   | Variável | Valor | Porquê |
   |---|---|---|
   | `N8N_NOTIFY` | `true` (padrão) | `false` desliga a notificação |
   | `N8N_BASE_URL` | `http://n8n:5678` **dentro do compose** (padrão `http://localhost:5678` para o app fora do Docker) | `localhost` dentro do container `radar` é o próprio container |
   | `N8N_WEBHOOK_PATH` | `webhook/radar-parecer` (padrão) | use `webhook-test/radar-parecer` só para testar com o editor em *Listen for test event* |

   Para uma demo rápida sem importar workflow, aponte `N8N_WEBHOOK_PATH` para o `webhook-test` e clique em **Execute workflow** antes de cada análise (a URL de teste desregistra após 1 disparo). Falha ao notificar (n8n fora, 404 do teste desarmado, timeout) é engolida — a análise conclui normalmente e o log registra `n8n_notify_failed`.

## Problemas comuns

| Sintoma | Causa | Correção |
|---|---|---|
| Parecer volta como "risco não avaliado" | `extract_requirement` não alcança o Ollama → requisito sem `search_terms` → nenhuma evidência coletada → `analyze_impact` vazio | `OLLAMA_BASE_URL` do serviço `radar` = `host.docker.internal`, não `localhost`; Ollama no host com `mistral` e `nomic-embed-text` baixados |
| `access to env vars denied` no node | n8n bloqueia `$env` nas expressões | `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` e recriar o container |
| `POST /analyze` dá *connection refused* | `RADAR_API_URL` resolveu para `localhost` dentro do n8n | tem que ser `http://radar:8000` |
| IF "Label é analise-impacto?" sempre *false* | payload de teste enviado como array `[ ... ]`, ou `label` no formato antigo (objeto `{ "name": "..." }`) | objeto único; a partir do card 52 `label` é a **string** `"analise-impacto"` e a 2ª condição compara `{{ $json.body.label }}` |
| Card do parecer não chega no Discord (fluxo da página) | notificação do card 52 desligada ou apontando pro lugar errado | `N8N_NOTIFY=true`; `N8N_BASE_URL=http://n8n:5678` dentro do compose; workflow `radar-parecer` importado e **Active**; ver `n8n_notify_failed` no log do serviço `radar` |
| Node Discord: `sendLegacy: undefined` / erro de TLS | bug de importação do node Discord v2 | trocar pelo **HTTP Request** (passo 5) |
| `webhook-test` retorna 404 | n8n não está escutando | clicar em **Listen for test event** antes do `curl`, ou usar a URL de produção com o workflow ativo |

## Estado da validação

`docker compose up` (API + n8n), importação do workflow e o caminho `webhook → IF → POST /analyze → HTTP Request → Discord` foram exercitados de ponta a ponta localmente — o parecer volta classificado e o card chega no canal do Discord (HTTP `204`). O disparo por Issue real do GitHub depende de expor a URL do n8n publicamente (túnel/host acessível), não exercitado aqui. A API que o workflow chama tem cobertura de teste E2E própria ([`tests/e2e/test_api.py`](../../tests/e2e/test_api.py), card 30).
