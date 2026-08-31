# Guia — Execução avançada

> Complementa a seção [Instalação e execução](../../README.md#instalação-e-execução) do README com os modos de execução que não são o caminho principal: rodar o grafo direto do Python, subir o servidor MCP isolado, compilar o frontend e rodar os testes contra serviços reais.

## Executando o grafo diretamente

```python
from src.graph.build import build_graph
from src.graph.state import create_initial_state

graph = build_graph()
state = create_initial_state("Adicionar filtro por data na listagem de pedidos")
resultado = graph.invoke(state)

print(resultado["requirement"].feature_type, resultado["risk_level"], resultado["confidence"])
```

Todos os nodes do grafo são reais — `analyze_impact` (card 44) e a composição do parecer final (`ImpactAnalysis` + prompt `04-compose-report`, card 45) foram as últimas peças a sair de stub. Sem `GITHUB_TOKEN`/`GITHUB_REPO` configurados, sem o modelo de embedding baixado, sem o Ollama no ar, ou se o Code/Commit Search do GitHub ainda não indexou o que foi procurado, a confiança calculada fica abaixo do threshold padrão (70) e o resultado escala para aprovação humana — degradação esperada (seção 11 do PRD), não uma falha. Quando não chega evidência nenhuma, `analyze_impact` não produz impacto nem risco: o parecer escala como **não avaliado** (`ESCALATED_NOT_ASSESSED`), com `risk_level` no piso `MEDIUM` e a tela/comentário mostrando "não avaliado" em vez de "Baixo" (card 46).

## Servidor MCP

```bash
python -m src.mcp_server.server
```

Sobe o servidor MCP via stdio. Tools registradas: `search_code` (card 08), `fetch_history` (card 09). `publish_comment` (card 10) existe em `src/mcp_server/tools/publish_comment.py` mas **não** é exposta como tool MCP — ela precisa do `AgentState` inteiro para validar a autorização (RF-08.2/RF-08.3), algo que um client MCP externo não pode fornecer com segurança; é chamada só pelo node do grafo.

## Frontend (TypeScript + Tailwind)

A lógica da página (`src/api/static/ts/*.ts` — `types.ts`, `api.ts`, `dom.ts`, `app.ts`) é escrita em TypeScript e compilada para `src/api/static/js/` (servido em `/static`), sem bundler — cada arquivo é um módulo ES nativo carregado pelo navegador. Estilo via Tailwind (CDN, paleta `rose`), sem CSS próprio. Depois de editar um `.ts`:

```bash
npm install   # uma vez
npm run build # ou "npm run watch" durante o desenvolvimento
```

O CI roda `tsc --noEmit` (job `typecheck-frontend`) a cada push/PR para pegar erro de tipo antes do merge; o JS compilado fica versionado no repositório (não há passo de build de frontend no Docker/CI) — rebuilde e commite o resultado sempre que mudar um `.ts`.

## Testes contra serviços reais

A suíte padrão (`python -m pytest -v`) não depende do Ollama nem do GitHub — o LLM e as tools externas são mockados. Para rodar também os smoke tests contra serviços reais:

```bash
RUN_OLLAMA_TESTS=1 python -m pytest tests/integration/test_extract_requirement_ollama.py -v
RUN_GITHUB_TESTS=1 python -m pytest tests/integration/test_search_code_github.py tests/integration/test_fetch_history_github.py -v
```
