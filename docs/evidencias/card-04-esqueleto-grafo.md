# Card 04 — Construir o esqueleto do grafo

**Branch/PR:** `feature/langgraph-agente` → [PR #5](https://github.com/scha-chan/radar-impact-agent/pull/5)
**Resultado esperado (Kanban):** Grafo executa ponta a ponta com stubs

## O que foi implementado

`src/graph/nodes.py` — nodes stub (sem LLM/API externa) para toda a topologia da seção 7 do PRD (`extract_requirement`, `guard_adversarial`, `block`, `search_codebase`, `retrieve_rag`, `fetch_history`, `analyze_impact`, `human_approval`, `publish_comment`, `archive`). Duas exceções, já reais:

- `score_risk` — reusa `src.domain.risk` (card 02) para calcular `risk_level`/`confidence` a partir do state
- `decide_autonomy`, `route_after_decision`, `route_after_approval` — lógica de roteamento definitiva (RF-06), não stub

`src/graph/build.py` — monta o `StateGraph`: execução sequencial, ramificação condicional (`guard_adversarial`, `decide_autonomy`, `human_approval`), paralelização via `Send` (fan-out para os três nodes de evidência, fan-in em `analyze_impact`).

`tests/integration/test_graph.py` — fan-out via `Send`, cada roteamento condicional testado isoladamente, e o grafo ponta a ponta para escalação por confiança baixa / aprovado → publica / rejeitado → arquiva.

## Prompt utilizado

> "Vá para o card 04"

## Decisões técnicas

- `score_risk` implementado de verdade (não stub) porque a lógica já existia pronta e testada desde o card 02 — não fazia sentido fingir um resultado fixo quando o cálculo real está disponível
- Conversão de tipos entre `graph/state.py` (strings) e `domain/risk.py` (`IntEnum`) isolada em `_to_risk_item`/`_RISK_LEVEL_NAME` dentro de `nodes.py` — mantém os dois módulos desacoplados, só `score_risk` conhece os dois formatos
- O teste que tentava validar o branch `block` invocando o grafo inteiro falhou: `guard_adversarial` (stub) sempre sobrescreve `is_adversarial` para `False`, mesmo que o estado inicial diga `True` — corrigido testando `_route_after_guard` isoladamente em vez de via `graph.invoke()`; o branch `block` só será testável ponta a ponta a partir do card 18 (detector adversarial real)
- `CONFIDENCE_THRESHOLD` lido via `os.getenv` diretamente em `nodes.py`, sem módulo de config dedicado — adiado até existir mais de uma variável de ambiente consumida fora de `api/`
