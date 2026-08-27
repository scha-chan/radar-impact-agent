# Card 48 — Camada de serviço no frontend: `RadarApiClient` + `UtilService`

**Branch/PR:** `feature/frontend-service-layer` → PR para `develop` (stacked sobre 44–47)
**Resultado esperado (Kanban):** revisão do frontend — chamadas externas isoladas numa classe e comandos de tela repetidos extraídos para um serviço utilitário.

## Motivação

`app.ts` tinha padrões copiados em várias telas: `document.querySelector<T>("#id")` com checagem de nulo (8×), `error instanceof ApiError ? error.message : "..."` (5×), `error instanceof ApiError && error.status === 404` (2×), toggle de botão ocupado (2×), o par `showMessage`/`hideMessage`. E as chamadas `fetch` estavam num módulo de funções soltas (`api.ts`), não numa classe.

## O que mudou

### `src/api/static/ts/service/radar-api-client.ts` (era `api.ts`)

`class RadarApiClient` — a **única porta de saída** da interface para a API. Todo `fetch` do front passa por aqui; nenhum outro módulo toca `fetch`/`XMLHttpRequest`. Métodos: `analyze`, `listPendingApprovals`, `submitApprovalDecision`, `getEscalationDetail`, `getAuditTrail`. `request<T>` privado centraliza cabeçalho, tratamento de `!response.ok` e o parse do `detail` do backend; lança `ApiError` (exportada). `constructor(baseUrl = "")` deixa a base configurável (testes/preview).

### `src/api/static/ts/service/util-service.ts` (novo)

- `UtilService.byId<T>(id)` — `querySelector` tipado por `#id`.
- `UtilService.errorMessage(error, fallback)` — `ApiError.message` (já traz o `detail` do backend) ou o fallback do contexto.
- `UtilService.isNotFound(error)` — `error instanceof ApiError && status === 404`.
- `UtilService.busy(button, run)` — desabilita o botão e troca o rótulo por "…" enquanto `run` executa; restaura no `finally`. Devolve o resultado.
- `UtilService.loading(container, msg?)` — placeholder de "carregando".
- `MessageBox.show/hide` — a faixa `#message-box`, compartilhada pelas três telas (era `showMessage`/`hideMessage` locais em `app.ts`).

Sem estado próprio; só encapsula o que estava duplicado. Construção segura de DOM continua em `dom.ts`, tradução/formatação em `i18n.ts`.

### `app.ts`

Instancia `const api = new RadarApiClient()` e passa a chamar `api.analyze(...)` etc. `handleAnalyzeSubmit` usa `UtilService.busy` (ganhou feedback "…" no botão, que antes não tinha). `refreshApprovals` usa `UtilService.loading`. Os `catch` usam `UtilService.errorMessage` / `UtilService.isNotFound`. `app.ts` não importa mais `ApiError` — a checagem ficou encapsulada.

### Backend

As chamadas externas do backend **já estavam isoladas** e não foram tocadas: GitHub via `src/mcp_server/tools/{search_code,fetch_history,publish_comment}.py` (httpx), LLM via `src/graph/llm.py::build_chat_model` (fábrica trocável por `LLM_PROVIDER`). `.gitignore` ganhou `*.db-shm`/`*.db-wal` (sidecars do SQLite do checkpointer).

## Testes

Não há runner de testes de JS no projeto. Verificação:

- `npm run build` e `npx tsc --noEmit` (job `typecheck-frontend` da CI): sem erro.
- `python -m pytest -q`: **350 passed, 6 skipped**, cobertura 99,50% — o contrato HTTP não mudou, os testes E2E de `/analyze` e `/approvals` seguem verdes.
- `ruff check` / `format --check`: limpos.
- JS compilado versionado (`src/api/static/js/`, com `js/service/`); `js/api.js` antigo removido.
