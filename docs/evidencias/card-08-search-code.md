# Card 08 — Implementar `search_code`

**Branch/PR:** `feature/mcp-github-tools`
**Resultado esperado (Kanban):** Arquivos e trechos retornados

## O que foi implementado

- `src/mcp_server/tools/search_code.py` — `search_code()`: busca cada termo (até 3) via API de busca de código do GitHub (`GET /search/code`, `Accept: application/vnd.github.text-match+json` para vir com trecho destacado), agrega e deduplica por caminho de arquivo, respeita `max_results`. RF-03.5: timeout de 10s, até 2 retries com backoff exponencial por termo; termo que esgota as tentativas é pulado (fallback) — nunca lança exceção
- `src/mcp_server/server.py` — `search_code` registrada como tool MCP (`@server.tool()`)
- `src/graph/nodes.py::search_codebase` — reescrito de stub para real; popula `code_matches` e, para RF-03.4, `evidence_sources` (uma entrada `type="code"` por arquivo encontrado)
- `src/graph/state.py` — `evidence_sources` passou a `Annotated[list[EvidenceSource], operator.add]`: os três nodes de evidência rodam em paralelo (fan-out via `Send`) e mais de um pode escrever nesse campo agora; sem reducer de acumulação o LangGraph rejeita a escrita concorrente na mesma chave. `code_matches`/`impact_patterns`/`change_history` não precisaram do mesmo tratamento — cada um é escrito por exatamente um node
- `src/config.py` — **gap corrigido**: nada carregava `.env` desde o card 06; `LLM_MODEL` etc. tinham default seguro e mascaravam o problema, mas `GITHUB_TOKEN` não tem default útil. `load_dotenv()` chamado por efeito colateral de import em `llm.py`, `search_code.py` e `server.py`

## Testes

- `tests/unit/test_search_code.py` — 6 testes com `respx` (sem rede real): retorna vazio sem repo/token, parse de match com snippet, dedupe entre termos, retry-então-sucesso, fallback após esgotar retries, respeito a `max_results`
- `tests/integration/test_search_code_github.py` — smoke test contra a API **real** do GitHub, pulado por padrão (`RUN_GITHUB_TESTS=1`); usa o token já autenticado do `gh` CLI local para os testes manuais, nunca um valor colado na conversa

## Evidência registrada

Smoke test contra a API real (repo `scha-chan/radar-impact-agent`, termo `"classify_risk"`):

```
tests/integration/test_search_code_github.py::test_search_code_against_real_github_repo PASSED
1 passed in 0.33s
```

A busca retornou 0 itens (`incomplete_results: true`) — não é falha: o Code Search do GitHub tem atraso de indexação após push, especialmente em repositórios novos. O teste foi ajustado para provar que a chamada autenticada funciona ponta a ponta (sem erro de auth/rede/parse), não que um arquivo específico já está indexado — asserção testando indexação imediata seria inerentemente instável.

Grafo completo end-to-end com a tool real ligada (token do `gh`, sem matches por indexação pendente): `feature_type=outro, code_matches=0, evidence_sources=[], confidence=10` — roda sem erro, `evidence_sources` como lista (reducer funcionando).

Suíte completa (sem os dois smoke tests): **58 passed in 1.54s**.

## Prompt utilizado

> "Sim, segue" (confirmação para avançar ao card 08, após o aviso de que seria necessário um `GITHUB_TOKEN` real para o smoke test)

## Decisões técnicas

- Um request HTTP por termo de busca (até 3), não um único request combinando todos — a API de busca de código do GitHub não suporta OR/agregação de termos na query clássica de forma confiável; múltiplos requests com timeout/retry independentes por termo é mais previsível
- `text_matches[0].fragment` usado como snippet em vez de buscar o conteúdo completo do arquivo — evita uma segunda chamada à API por resultado; aceita que o trecho pode ficar truncado
- `line: None` em todo `CodeMatch` — a API de busca de código não retorna número de linha, só o fragmento de texto; documentado como limitação (já prevista na seção 25 do PRD: "busca de código é textual, não semântica")
- Token usado nos testes manuais veio de `gh auth token` (já autenticado nesta máquina para o fluxo de PRs), nunca inserido diretamente — evita expor segredo em texto de conversa ou em arquivo versionado
