# Card 21 — Investigar uma execução real

**Resultado esperado (Kanban):** Demonstrar correlação → Reconstrução documentada

## Execução investigada

Rodada real (não simulada em teste) do grafo completo (`build_graph().invoke()`) contra o Ollama local (`mistral`), com `configure_structured_logging()` (card 19) ligado e a trilha de auditoria (card 20) gravando no caminho padrão. Nenhum LLM foi mockado — os dois nodes que chamam modelo (`extract_requirement`, `guard_adversarial`) rodaram de verdade.

**Requisito de entrada:**

> "Adicionar autenticação por 2FA no login." — o mesmo texto de exemplo do cenário 2 (seção 12 do PRD).

**Ambiente no momento da execução** (relevante para interpretar o resultado): sem `.env` configurado — `GITHUB_TOKEN`/`GITHUB_REPO` ausentes, e o Ollama local tinha `mistral`/`gemma4:12b` instalados mas **não** `nomic-embed-text` (`OLLAMA_EMBED_MODEL`). Isso é o que explica evidência de código/histórico/RAG vazia abaixo — não é um resultado forjado, é o comportamento real do sistema num ambiente sem essas duas dependências opcionais configuradas, e é justamente o tipo de situação que a fórmula de confiança (seção 11 do PRD) foi desenhada para penalizar.

`session_id = 95b8967f` (compartilhado por log e auditoria, RF-09.1/RF-09.3 — é a correlação que este card pede para demonstrar).

## Linha do tempo dos nodes

Reconstruída diretamente dos eventos `node_completed` (sinal 1, card 19), na ordem em que aconteceram:

| # | Node | Status | Duração | O que aconteceu |
|---|---|---|---|---|
| 1 | `extract_requirement` | ok | **11.588,08 ms** | Chamada real ao Ollama (`mistral`) — de longe o node mais lento; classificou `feature_type="login"` corretamente e extraiu `search_terms=["autenticacao", "2FA", "login"]` |
| 2 | `guard_adversarial` | ok | **4.078,67 ms** | Camada 1 (padrões, card 18) não encontrou nada → camada 2 chamou o Ollama de novo; classificou como não adversarial |
| 3 | `search_codebase` | ok | 0,30 ms | `search_code_missing_config` (log de `search_code.py`) — sem `GITHUB_REPO`/`GITHUB_TOKEN`, retorna `[]` imediatamente, sem tentar rede; `code_matches_count=0` |
| 4 | `fetch_history` | ok | 0,07 ms | Mesmo motivo de (3): `change_history_count=0` |
| 5 | `retrieve_rag` | ok | **2.117,50 ms** | Tentou embedar a consulta via Ollama (`retrieve_patterns_failed`, log de `retriever.py`) — `nomic-embed-text` não está instalado, a chamada falhou depois de ~2,1s de round-trip real; capturado pelo fallback (RF-03.5), `impact_patterns_count=0` |
| 6 | `analyze_impact` | ok | 0,00 ms | Ainda stub (card 14 do LLM, pendente) — `impacts`/`risks` vazios |
| 7 | `score_risk` | ok | 0,02 ms | Determinístico (`domain/risk.py`, card 02) |
| 8 | `decide_autonomy` | ok | 0,48 ms | Decide escalar — grava `approval_expires_at` (card 16) e a entrada de auditoria `ESCALATED` (ver abaixo) |
| 9 | `human_approval` | **paused** | 0,02 ms | `interrupt()` real (card 15) — a execução pausou aqui; não há node 10 porque `publish_comment`/`archive` nunca rodaram nesta invocação |

**Latência total: 17.792,63 ms.** Os dois nodes que chamam LLM (`extract_requirement` + `guard_adversarial`) somam **15.666,75 ms — 88% do tempo total**; a tentativa de embedding do RAG soma mais 2.117,50 ms (12%). Todo o resto do grafo (sete nodes determinísticos ou de I/O local) executa em menos de 1 ms somado. Essa é a evidência concreta de onde o orçamento de execução (RF-06.5, card 35, ainda não implementado) precisaria focar se fosse necessário: não há gargalo estrutural no grafo, o custo inteiro é chamada de modelo.

## Eventos JSON reais (sinal 1 — log estruturado)

```json
{"session_id": "95b8967f", "correlation_id": "95b8967f", "node": "extract_requirement", "status": "ok", "duration_ms": 11588.08, "event": "node_completed", "timestamp": "2026-08-26T20:12:48.398609Z", "level": "info"}
{"session_id": "95b8967f", "correlation_id": "95b8967f", "node": "guard_adversarial", "status": "ok", "duration_ms": 4078.67, "event": "node_completed", "timestamp": "2026-08-26T20:12:52.477806Z", "level": "info"}
{"session_id": "95b8967f", "correlation_id": "95b8967f", "node": "search_codebase", "status": "ok", "duration_ms": 0.3, "code_matches_count": 0, "evidence_sources_count": 0, "tools_failed_count": 0, "event": "node_completed", "timestamp": "2026-08-26T20:12:52.479495Z", "level": "info"}
{"session_id": "95b8967f", "correlation_id": "95b8967f", "node": "fetch_history", "status": "ok", "duration_ms": 0.07, "change_history_count": 0, "evidence_sources_count": 0, "tools_failed_count": 0, "event": "node_completed", "timestamp": "2026-08-26T20:12:52.480179Z", "level": "info"}
{"session_id": "95b8967f", "correlation_id": "95b8967f", "node": "retrieve_rag", "status": "ok", "duration_ms": 2117.5, "impact_patterns_count": 0, "evidence_sources_count": 0, "event": "node_completed", "timestamp": "2026-08-26T20:12:54.597155Z", "level": "info"}
{"session_id": "95b8967f", "correlation_id": "95b8967f", "node": "analyze_impact", "status": "ok", "duration_ms": 0.0, "impacts_count": 0, "risks_count": 0, "dependencies_count": 0, "recommended_tests_count": 0, "event": "node_completed", "timestamp": "2026-08-26T20:12:54.597724Z", "level": "info"}
{"session_id": "95b8967f", "correlation_id": "95b8967f", "node": "score_risk", "status": "ok", "duration_ms": 0.02, "event": "node_completed", "timestamp": "2026-08-26T20:12:54.597998Z", "level": "info"}
{"session_id": "95b8967f", "correlation_id": "95b8967f", "node": "decide_autonomy", "status": "ok", "duration_ms": 0.48, "event": "node_completed", "timestamp": "2026-08-26T20:12:54.598678Z", "level": "info"}
{"session_id": "95b8967f", "correlation_id": "95b8967f", "node": "human_approval", "status": "paused", "duration_ms": 0.02, "event": "node_completed", "timestamp": "2026-08-26T20:12:54.599093Z", "level": "info"}
```

## Entrada real da trilha de auditoria (sinal 2)

```json
{"timestamp": "2026-08-26T20:12:54.598562+00:00", "session_id": "95b8967f", "decision": "ESCALATED", "risk_level": "LOW", "confidence": 25, "threshold": 70, "actor": "system", "tool_authorized": null}
```

## Correlação entre os dois sinais

O `session_id` (`95b8967f`) é idêntico nos dois sinais — é a chave que permite reconstruir esta execução a partir de qualquer um dos dois independentemente. Além disso, o **timestamp da entrada de auditoria** (`20:12:54.598562Z`) cai a menos de 1 décimo de milissegundo do **timestamp do evento de log do node que a gerou**, `decide_autonomy` (`20:12:54.598678Z`) — confirmando que a auditoria foi escrita de dentro do próprio node, no mesmo instante em que a decisão foi tomada, não em um processo assíncrono desacoplado que poderia perder a correlação temporal.

## A decisão de autonomia e a evidência que a sustentou

**Decisão:** `ESCALATED` — o parecer não foi publicado sozinho; a execução pausou em `human_approval` aguardando aprovação humana (`interrupt()`, cards 15/16).

**Por que a confiança ficou em 25** (fórmula da seção 11 do PRD, `calculate_confidence`, card 02/14) — reconstruída dedução por dedução a partir da evidência real coletada nos nodes 1–5 acima:

| Dedução | Valor | Evidência (de qual node) |
|---|---|---|
| Base | 100 | — |
| Requisito com menos de 15 palavras (6: "Adicionar autenticação por 2FA no login.") | −20 | `extract_requirement` (node 1) |
| Nenhum arquivo encontrado na busca de código | −25 | `search_codebase` (node 3): `code_matches_count=0` |
| Tipo de feature "outro"? Não, é "login" | 0 | `extract_requirement` (node 1) |
| Nenhum padrão RAG recuperado acima do limiar | −20 | `retrieve_rag` (node 5): `impact_patterns_count=0` |
| Tool com fallback por falha (RF-03.5) | 0 | `tools_failed=[]` — ausência de config não conta como falha de tool, é distinto de esgotar retries |
| Menos de duas fontes distintas em `evidence_sources` | −10 | `evidence_sources_count=0` em todos os nodes de evidência |
| Riscos sem mitigação | 0 | `analyze_impact` (node 6) ainda não gera riscos (stub, card 14 do LLM) |
| **Total** | **25** | `100 − 20 − 25 − 20 − 10 = 25` |

`25 < CONFIDENCE_THRESHOLD (70)` → `decide_autonomy` (RF-06) força `human_review_required=True`, grava `approval_expires_at` (card 16) e a entrada `ESCALATED` na trilha de auditoria — exatamente o que a linha do tempo e a entrada de auditoria acima registram.

## O que esta investigação demonstra

1. **Os dois sinais de observabilidade (cards 19 e 20) realmente se correlacionam** por `session_id`, com precisão de sub-milissegundo entre o evento de log e o registro de auditoria do mesmo node.
2. **A decisão de autonomia é rastreável até a evidência bruta** — cada dedução da fórmula de confiança aponta para um campo concreto de um node concreto, não para um número solto.
3. **O sistema degrada de forma correta, não silenciosa**, quando dependências opcionais (`GITHUB_TOKEN`, modelo de embedding) não estão configuradas: em vez de falhar ou de publicar um parecer sem evidência, a confiança cai e a execução escala para revisão humana — o comportamento exigido por RF-06.2.
4. **O custo real de uma execução é dominado por chamadas de LLM** (88% do tempo em dois nodes), não pela orquestração do grafo em si — achado relevante para qualquer trabalho futuro de orçamento de execução (card 35).
