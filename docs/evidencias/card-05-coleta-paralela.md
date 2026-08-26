# Card 05 — Implementar a coleta paralela de evidência

**Branch/PR:** `feature/langgraph-agente`
**Resultado esperado (Kanban):** Três nodes concorrentes com medição de latência

## O que foi implementado

O fan-out via `Send` já existia desde o card 04 (`_route_after_guard` em `src/graph/build.py`); faltava provar e medir que os três nodes de evidência (`search_codebase`, `retrieve_rag`, `fetch_history`) realmente rodam em paralelo, não em série — exigência de RNF-04.

- `src/graph/nodes.py`: `STUB_IO_LATENCY_SECONDS = 0.1` — latência de I/O simulada nos três nodes de evidência, só para a comparação ser mensurável antes das integrações reais (cards 8, 9, 13) existirem
- `tests/integration/test_evidence_parallelism.py`: mede o tempo de rodar os três nodes isoladamente em sequência vs. o tempo do grafo completo (fan-out via `Send`), com asserção de que o grafo é significativamente mais rápido que a soma sequencial

## Evidência registrada (RNF-04)

```
sequencial (3 nodes isolados): 301.3ms
grafo completo (Send + demais nodes): 106.4ms
razão: 0.35x
```

O grafo completo — que inclui `extract_requirement`, `guard_adversarial`, `analyze_impact`, `score_risk` e `decide_autonomy` além dos três nodes de evidência — roda em ~1/3 do tempo que os três nodes de evidência levariam rodando em sequência sozinhos. Prova que o `Send` está de fato paralelizando, não serializando.

## Prompt utilizado

> "Vá para o card 05"

## Decisões técnicas

- Latência artificial (`time.sleep`) em vez de mock de rede — mais simples e determinístico para provar concorrência; será removida node a node conforme as integrações reais (cards 8, 9, 13) trouxerem sua própria latência de rede para medir
- Limiar do teste (`< sequencial * 0.8`) deliberadamente frouxo — o objetivo é provar que não está serializando, não fixar um número de performance; um limiar apertado (ex. `< 0.4x`) tornaria o teste instável em CI sob carga variável
- Não foi adicionado campo de duração por node no `AgentState` — pertence a RF-09.1 (logs estruturados, card 19), não a este card; medir a latência agregada da coleta paralela é suficiente para RNF-04
