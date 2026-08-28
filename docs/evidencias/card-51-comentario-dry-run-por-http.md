# Card 51 — Servir o parecer DRY_RUN por HTTP (link "Ver comentário publicado")

**Branch/PR:** `feature/dry-run-comment-endpoint` → PR para `develop` (stacked sobre o card 50)
**Resultado esperado (Kanban):** o link "Ver comentário publicado" da página abre o parecer.

## O que acontecia

Quando o parecer é publicado de verdade numa Issue, `publish_comment` devolve a
`html_url` do GitHub e o link funciona. Mas em **`DRY_RUN`** (padrão) ou sem
`issue_number`, o parecer é gravado em `audit/dry_run/{session_id}.md` e a tool
devolve `file://audit/dry_run/{session_id}.md`. A página coloca isso direto no
`href` — e um link `file://`, ainda por cima com caminho relativo, **não abre a
partir de uma página `http://`** (o navegador bloqueia). Clicar não fazia nada.

## O que foi implementado

### API (`src/api/app.py`)

- **`GET /comment/{session_id}`** (novo) — lê `audit/dry_run/{session_id}.md` e
  devolve o conteúdo como `text/markdown; charset=utf-8` (`PlainTextResponse`);
  404 se não existir. `DRY_RUN_COMMENT_DIR` é a mesma constante que
  `publish_comment._write_dry_run_file` usa por padrão.
- **`_comment_url(session_id, result)`** — no `_to_analyze_response`: se
  `published_comment_url` começa com `file://`, troca por `/comment/{session_id}`;
  uma `https://…` (publicação real) passa intacta. O `AgentState` continua
  guardando o `file://` internamente — só a resposta HTTP é reescrita, então os
  testes de grafo que leem `result["published_comment_url"]` não mudam.

### Frontend (`src/api/static/ts/app.ts`, JS recompilado)

- O link ganhou `target="_blank"` + `rel="noopener"` e o rótulo passa a ser
  **"Ver parecer (DRY_RUN)"** quando aponta para `/comment/…`, ou
  **"Ver comentário publicado"** quando é uma URL do GitHub.

## Testes

- **`tests/e2e/test_api.py`**: `POST /analyze` (caminho feliz) → `published_comment_url`
  é `/comment/{session_id}`; `GET /comment/{id}` → 200 com o texto do parecer e
  `content-type: text/markdown`; sessão desconhecida → 404. As duas asserções
  antigas que esperavam `startswith("file://")` na **resposta HTTP** passaram a
  esperar `/comment/…`.
- Os testes de grafo (`test_scenario_2` etc.) que inspecionam o `file://` no
  `AgentState` seguem inalterados.

`python -m pytest -q`: **392 passed, 6 skipped**, cobertura **99,48%** (100% em
`src/api/app.py`). `ruff check` / `format --check` + `npm run build`/`tsc --noEmit`:
sem apontamentos.
