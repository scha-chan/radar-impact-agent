# Card 43 — Repositório do GitHub por execução

**Branch/PR:** `feature/repo-per-run` → PR para `develop` (stacked sobre 44–49)
**Resultado esperado (Kanban):** um campo na tela para informar o repositório do GitHub, permitindo testar o agente contra fontes diferentes sem mexer no `.env`.

## O que acontecia

`GITHUB_REPO` era fixo no ambiente — o único repositório que `search_codebase`/`fetch_history`/`publish_comment` conseguiam consultar. Para testar outra fonte era preciso editar o `.env` e reiniciar o servidor.

## O que foi implementado

### Normalização — `src/graph/github_repo.py` (novo)

`normalize_github_repo(value) -> str | None`: aceita `owner/repo`, `https://github.com/owner/repo` (com/sem `.git` e barra final), `github.com/owner/repo` e `git@github.com:owner/repo.git`; devolve `owner/repo`. `None`/vazio → `None`. Formato não reconhecido → `ValueError`.

### Estado e nodes

- **`AgentState.github_repo: str | None`** e `create_initial_state(..., github_repo=None)` (`src/graph/state.py`).
- **`nodes._effective_github_repo(state)`** — `state["github_repo"] or os.getenv("GITHUB_REPO", "")`. Os três nodes que falam com o GitHub (`search_codebase`, `fetch_history`, `publish_comment`) passaram a usá-lo no lugar de `os.getenv("GITHUB_REPO", "")` direto. O `GITHUB_TOKEN` continua vindo só do ambiente e precisa ter acesso ao repositório informado.

### API

- **`AnalyzeRequest.repo: str | None`** (`src/api/schemas.py`), com `field_validator` chamando `normalize_github_repo` — entrada inválida vira **422**.
- **`AnalyzeResponse.github_repo`** — o repositório de fato analisado (o informado ou o do ambiente), para a tela confirmar qual fonte foi usada.
- `analyze` passa `github_repo=request.repo` a `create_initial_state`.

### Frontend (`src/api/static/*`, JS recompilado)

- **`index.html`**: campo de texto "Repositório do GitHub (opcional)" **antes** do campo de Issue, com placeholder `owner/repo ou https://github.com/owner/repo` e uma nota de que vazio usa o repositório do servidor e que é preciso `GITHUB_TOKEN` com acesso.
- **`app.ts`**: `handleAnalyzeSubmit` inclui `repo` no payload quando preenchido; `renderAnalyzeResult` mostra a linha "repositório analisado".
- **`types.ts`**: `AnalyzeRequest.repo?`, `AnalyzeResponse.github_repo`.

## Testes

- **`tests/unit/test_github_repo.py`** (novo): `normalize_github_repo` — 13 formatos aceitos + 5 rejeitados.
- **`tests/unit/test_github_repo_override.py`** (novo): `_effective_github_repo` (state > env > vazio); `search_codebase`/`fetch_history` repassam o repo do state à tool.
- **`tests/e2e/test_api.py`**: `POST /analyze` com `repo` URL → normalizado e ecoado em `github_repo`, sobrepondo o do ambiente; sem `repo` → fallback para o `GITHUB_REPO`; `repo` inválido → 422.
- **`tests/unit/test_state.py`**: `github_repo` no default e no override de `create_initial_state`.

`python -m pytest -q`: **387 passed, 6 skipped**, cobertura **99,53%** (100% em `github_repo.py` / `nodes.py` / `state.py` / `app.py` / `schemas.py`). `ruff` + `npm run build`/`tsc --noEmit`: limpos.

Smoke via `TestClient`: `repo: "github.com/acme/widgets"` → `search_code` recebeu `repo="acme/widgets"`; sem `repo` → `GITHUB_REPO` do ambiente; `repo: "lol"` → 422.
