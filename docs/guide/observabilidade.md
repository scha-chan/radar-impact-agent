# Guia — Observabilidade e orçamento de execução

> Detalhamento da seção [QA, observabilidade e DevOps](../../README.md#qa-observabilidade-e-devops) do README.

## Os três sinais e uma investigação real

Toda execução emite três sinais correlacionados pelo mesmo `session_id`/`correlation_id` (seção 14 do PRD):

- **Log estruturado (JSON)** — um evento `node_completed` por node, com `status` e `duration_ms`. Ligar o renderer JSON de verdade:

  ```python
  from src.observability.logging import configure_structured_logging
  configure_structured_logging()
  ```

- **Trilha de auditoria (JSONL)** — um registro por decisão de autonomia (`ESCALATED`, `ESCALATED_BUDGET_EXCEEDED`, `ESCALATED_NOT_ASSESSED`, `REANALYSIS_REQUESTED`, `AUTO_PUBLISHED`, `APPROVED_PUBLISHED`, `BLOCKED_ADVERSARIAL`, `REJECTED_ARCHIVED`, `EXPIRED_ARCHIVED`, `PUBLISH_DENIED`), gravado em `AUDIT_LOG_PATH` (padrão `audit/trail.jsonl`). O painel `GET /approvals` da interface mínima deriva desse mesmo arquivo.

- **Trace OpenTelemetry (card 35)** — um span por node (RF-09.2), seguindo as convenções semânticas GenAI (`gen_ai.operation.name`, `gen_ai.request.model`, `gen_ai.tool.name`, RF-09.6) nos nodes que chamam LLM ou tool. Todo span carrega `agent.version`/`prompt.version`/`policy.version` fixos (RF-09.5) — sem eles, uma regressão de comportamento não seria rastreável até a versão que a causou. A chamada HTTP de saída das tools (`search_code`/`fetch_history`/`publish_comment`) propaga o contexto do span corrente via W3C Trace Context (header `traceparent`, RF-09.6). Desligado por padrão (`OTEL_CONSOLE_EXPORT=false`); ligar o exporter de console:

  ```bash
  OTEL_CONSOLE_EXPORT=true python -m src.api.app
  ```

Uma execução real reconstruída — linha do tempo dos nove nodes com latência de cada um, a decisão de autonomia tomada e a evidência que a sustentou, com os sinais correlacionados por `session_id` — está documentada em [`docs/evidencias/card-21-investigacao-execucao-real.md`](../evidencias/card-21-investigacao-execucao-real.md) (os dois primeiros sinais; o trace é posterior, card 35).

## Orçamento de execução (RF-06.5, card 35)

Nenhuma execução roda indefinidamente. `AgentState.steps_taken`/`max_steps` (padrão 12) e o relógio de parede (`MAX_WALL_TIME_SECONDS`, padrão 60s) são checados em `budget_gate` — entre o fan-in de evidência e `analyze_impact` — e de novo em `decide_autonomy` (rede de segurança para o caso do orçamento estourar já dentro de `analyze_impact`/`score_risk`). Estourar qualquer um força `human_review_required=true` e `risk_level` mínimo `MEDIUM` (nunca rebaixa um risco já mais grave), pulando `analyze_impact`/`score_risk` de propósito — o requisito nunca é publicado como se tivesse sido totalmente analisado. A auditoria registra `ESCALATED_BUDGET_EXCEEDED` com `steps_taken`/`max_steps`/`duration_seconds`. Detalhes e decisões de arquitetura em [`docs/evidencias/card-35-orcamento-execucao-versionamento-spans.md`](../evidencias/card-35-orcamento-execucao-versionamento-spans.md).
