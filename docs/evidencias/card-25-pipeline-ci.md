# Card 25 — Pipeline CI

**Branch/PR:** `feature/ci-pipeline`
**Resultado esperado (Kanban):** Lint, testes, build → Workflow verde

## O que foi implementado

- `.github/workflows/ci.yml` (novo) — quatro jobs, seção 16 do PRD:
  - **lint** — `ruff check .` e `ruff format --check .`
  - **test** — `pytest --cov --cov-report=term-missing` (o gate de 70%, card 22, já vem de `pyproject.toml`)
  - **build** — `docker build -t radar:ci .`, depende de lint+test passarem primeiro
  - **secrets-scan** — `gitleaks` via imagem Docker oficial (`zricethezav/gitleaks:latest`), evitando depender de uma action de terceiros no marketplace
  - Gatilhos: `push` para `develop` (o que a seção 16 do PRD pede) e `pull_request` para **`develop` e `main`** — adicionado `develop` porque é para lá que todo PR de feature branch deste projeto aponta (o fluxo real: `feature/*` → PR → `develop`, `develop` → `main` só no card 34 final); restringir a `main` como a seção 16 sugere deixaria a CI muda em 33 dos 34 cards do projeto, sem nunca rodar num PR de verdade até a entrega.
- `Dockerfile` (novo) — `python:3.12-slim`, instala `requirements.txt`, copia `src/` e `knowledge/`. Sem API ainda (card 30), o entrypoint padrão é o servidor MCP (`python -m src.mcp_server.server`, card 07).
- `docker-compose.yml` (novo, RNF-06) — um serviço, `.env` carregado via `env_file`, `OLLAMA_BASE_URL` apontando para o host (`host.docker.internal`, já que o Ollama roda fora do container), e um volume único (`radar-data`) para os três caminhos que o app grava (`CHROMA_PERSIST_DIR`, `CHECKPOINT_DB_PATH`, `AUDIT_LOG_PATH`) — sobrescritos via `environment` para caírem todos dentro do volume montado.
- `.dockerignore` (novo) — exclui `tests/`, `docs/`, `.git/`, dados locais (`chroma/`, `audit/`, `*.db`) do contexto de build.
- `pyproject.toml` ganhou `[tool.ruff] line-length = 100` — sem isso, `ruff format --check .` reprovaria 36 dos 67 arquivos do projeto (o padrão do ruff é 88 colunas; comentários/docstrings em português tendem a passar disso). `ruff format .` rodado uma vez sobre o repositório inteiro para conformar os 19 arquivos que ainda ficavam acima de 100 colunas — mudança puramente cosmética (quebra de linha), confirmada pela suíte inteira continuando verde sem alteração.
- README ganhou o badge de status do workflow.

## Por que `line-length = 100`, não o padrão 88

O projeto é escrito com comentários e docstrings extensos em português (parte do estilo de documentação já estabelecido desde o card 01), que naturalmente ultrapassam 88 colunas com frequência. Adotar o padrão do ruff sem ajuste forçaria uma reformatação muito mais agressiva (quebrando comentários no meio de frases) só para caber num limite arbitrário que não reflete o estilo real do código. 100 colunas é o ponto em que a maioria dos arquivos já se encaixava naturalmente (48 de 67 antes de rodar `ruff format`).

## Por que gitleaks via Docker, não a action do marketplace

`gitleaks/gitleaks-action` teve mudanças de licenciamento (passou a exigir licença paga para uso comercial via GitHub App em alguns contextos) — rodar a imagem Docker oficial (`zricethezav/gitleaks:latest`) diretamente com `detect --source . --no-banner` evita qualquer ambiguidade de licenciamento e não depende de uma action de terceiros ficar disponível/atualizada no marketplace.

## Testes

`pytest -q`: 167 passed, 3 skipped (Ollama real), 99,10% de cobertura — suíte não depende de Docker, Ollama real nem `GITHUB_TOKEN` para passar (os testes que precisam desses recursos já eram condicionados a env vars, `RUN_OLLAMA_TESTS`/`RUN_GITHUB_TESTS`, README seção "Rodando os testes"). `ruff check .` e `ruff format --check .`: sem apontamentos, repositório inteiro.

Build do Docker (`docker build -t radar:ci .`) não pôde ser testado localmente (Docker não disponível no ambiente de desenvolvimento) — validado pela execução real do workflow no GitHub Actions após o push (link do run: ver o badge de CI no README, ou a aba Actions do repositório).

## Decisões técnicas

- `build` depende de `lint`+`test` (`needs: [lint, test]`) — não faz sentido gastar tempo de build de imagem se o lint ou os testes já reprovaram; falha rápido primeiro.
- `secrets-scan` roda em paralelo aos demais (não é `needs` de ninguém) — é uma checagem independente do conteúdo versionado, não do código rodando.
- Python `3.13` na CI, não `3.14` (usado localmente) — `3.14` é recente demais para garantir disponibilidade estável nos runners hospedados do GitHub no momento deste PR; o projeto não usa nenhuma sintaxe exclusiva de `3.14`, então não há perda de cobertura real.
