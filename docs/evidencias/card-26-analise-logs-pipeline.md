# Card 26 — Análise de logs do pipeline com IA

**Branch/PR:** `docs/analise-logs-pipeline`
**Resultado esperado (Kanban):** Explicar duas etapas → `/docs/devops/analise-logs.md`

## O que foi feito

Análise com IA de logs **reais** de duas etapas do pipeline de CI (card 25): `test` e `build`, usando as execuções reais do GitHub Actions do próprio card 25 ([run que falhou](https://github.com/scha-chan/radar-impact-agent/actions/runs/33013041270) e [run que passou](https://github.com/scha-chan/radar-impact-agent/actions/runs/33013358793)), obtidas via `gh run view --log`.

Entregável principal: **[`docs/devops/analise-logs.md`](../devops/analise-logs.md)** — log bruto, explicação produzida e o que foi corrigido, para cada uma das duas etapas.

## Resumo

**Etapa `test`:** 46 warnings no relatório do pytest, dois vetores reais: conexões sqlite não fechadas nos testes de checkpointer (cards 15/16/22/23) e dublês de `EmbeddingFunction` (ChromaDB) não implementando o protocolo completo. Corrigido: `tests/helpers.py::sqlite_checkpointer`/`close_all_sqlite_connections` + fixture `autouse` em `conftest.py` fecham as conexões automaticamente; os dublês ganharam `__init__`/`name()`/`get_config()`. Resultado: 46 → 12 warnings. Uma tentativa adicional (`build_from_config()`) foi revertida por piorar o comportamento — documentado como ponto de parada consciente.

**Etapa `build`:** o `docker build` passava, mas o `pip` avisava sobre rodar como root — o Dockerfile não definia nenhum `USER`, então o processo da aplicação em tempo de execução também rodava como root. Corrigido: `Dockerfile` ganhou um usuário sem privilégios (`useradd`/`USER radar`) para o `CMD` final, mantendo a instalação de dependências como root (necessária para escrever no `site-packages` do sistema). Limitação conhecida documentada: quando a API (card 30) existir e precisar escrever em volumes montados, será preciso ajustar a propriedade do diretório.

## Por que reverter uma correção também é parte do processo

A tentativa de eliminar os 12 warnings restantes do ChromaDB (adicionando `build_from_config()` aos dublês) introduziu um erro pior — uma interação da versão `1.5.9` do `chromadb` chamando `name()` sem instância. Reconhecer que uma correção piorou o comportamento e revertê-la, em vez de forçar a passagem, é o mesmo tipo de julgamento crítico que o card 24 (code review) já havia demonstrado — vale registrar aqui também, porque "o que foi corrigido" inclui saber quando parar.

## Testes

`pytest -q`: 167 passed, 3 skipped (Ollama real), 99,10% de cobertura, sem regressão. `ruff check .`/`ruff format --check .`: sem apontamentos. Build do Docker validado por uma nova execução real do CI (ver PR deste card).
