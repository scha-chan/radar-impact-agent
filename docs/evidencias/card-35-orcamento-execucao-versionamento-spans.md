# Card 35 — Orçamento de execução e versionamento em spans

**Branch/PR:** `feature/execution-budget-and-tracing`
**Extensão pós-rubrica** (seção 21 do PRD) — RF-06.5, RF-09.5, RF-09.6.

## O que foi implementado

### RF-06.5 — Orçamento de execução

- `src/graph/state.py`: `AgentState` ganha `steps_taken` (soma via `operator.add`, mesmo padrão de `evidence_sources`/`tools_failed` — os três nodes de evidência rodam em paralelo via `Send` e cada um contribui `+1`), `max_steps` (padrão `MAX_STEPS=12`) e `started_at`. `create_initial_state` aceita `max_steps` como parâmetro, para os testes forçarem o estouro sem precisar de mocks lentos.
- `src/graph/budget.py` (novo): `count_step` incrementa `steps_taken` a cada node concluído (mesmo ponto único de instrumentação de `log_node_execution`, card 19 — sem tocar `nodes.py` a cada node novo); `is_budget_exceeded`/`elapsed_seconds` checam `steps_taken >= max_steps` ou o relógio de parede contra `MAX_WALL_TIME_SECONDS` (padrão 60s).
- Novo node `budget_gate` (`graph/nodes.py`), inserido entre o fan-in dos três nodes de evidência e `analyze_impact` (`graph/build.py`): se o orçamento já estourou ali, `_route_after_budget_gate` desvia direto para `decide_autonomy`, **pulando `analyze_impact`/`score_risk` de propósito** — "nunca deixa o requisito passar como se tivesse sido totalmente analisado" (cenário 5 do PRD).
- `decide_autonomy` ganha uma segunda checagem do orçamento (rede de segurança para o caso de estourar só durante `analyze_impact`/`score_risk`, depois de `budget_gate` já ter deixado passar): se estourado, força `risk_level` mínimo `MEDIUM` (nunca rebaixa um risco já mais grave — `HIGH`/`CRITICAL` ficam como estão) e `human_review_required=true`, registrando `ESCALATED_BUDGET_EXCEEDED` na auditoria em vez de `ESCALATED`.
- `AuditRecord`/`AuditDecision` (`observability/audit.py`) ganham a decisão `ESCALATED_BUDGET_EXCEEDED` e os campos opcionais `steps_taken`/`max_steps`/`duration_seconds` (só presentes nessa decisão — cenário 5: "auditoria registra... com steps_taken/max_steps e a duração real"). `list_pending_sessions` (RF-10.2) passa a tratar `ESCALATED_BUDGET_EXCEEDED` como pendente de aprovação, do mesmo jeito que `ESCALATED`.

### RF-09.5 — Versionamento fixo

- `AgentState` ganha `agent_version`/`prompt_version`/`policy_version`, lidos de `AGENT_VERSION`/`PROMPT_VERSION`/`POLICY_VERSION` (env, com default) em `create_initial_state` — não de uma constante global lida direto por quem grava o log/span/auditoria, para a versão registrada ser a que estava em vigor quando a execução **começou**, mesmo que o processo seja atualizado com a execução já em andamento.
- `observability/tracing.py::version_attributes` exporta esses três campos como atributos de span (`agent.version`/`prompt.version`/`policy.version`).

### RF-09.6 — Spans OpenTelemetry e W3C Trace Context

- `observability/tracing.py` (novo, terceiro sinal de observabilidade, ortogonal ao log estruturado — RF-09.1, card 19 — e à trilha de auditoria — RF-09.3, card 20): `trace_node` abre um span por node (RF-09.2), com os atributos de versão (RF-09.5) e `session.id`/`correlation.id`. `configure_tracing()` registra o `TracerProvider` (exporta para console só com `OTEL_CONSOLE_EXPORT=true`, desligado por padrão — mesma ideia de `configure_structured_logging`).
- `graph/build.py`: todo node passa por `log_node_execution(name, trace_node(name, count_step(fn)))` — os três sinais de observabilidade (log, orçamento, trace) compartilham o único ponto de instrumentação já estabelecido no card 19.
- `graph/nodes.py`: `extract_requirement`/`guard_adversarial` (chamada LLM) setam `gen_ai.operation.name="chat"`/`gen_ai.request.model` no span corrente; `search_codebase`/`fetch_history`/`publish_comment` (chamada tool) setam `gen_ai.tool.name`. `gen_ai.usage.input_tokens`/`output_tokens` ficam de fora conscientemente — documentado no docstring de `_set_gen_ai_span_attributes`: `with_structured_output` (LangChain) devolve o Pydantic já parseado, não o `AIMessage` com `usage_metadata`, e trocar a chamada só para capturar contagem de tokens não valeria a troca aqui.
- `mcp_server/tools/_http.py::traceparent_headers()` injeta o header `traceparent` (W3C Trace Context) a partir do span ativo — usado por `get_with_retry` (GET, `search_code`/`fetch_history`) e por `publish_comment._publish_via_github_api` (POST direto).

## Decisão de arquitetura: o que "propagar contexto da API ao servidor MCP" significa aqui

O PRD descreve RF-09.6 como "a chamada da API ao servidor MCP propaga contexto via W3C Trace Context, para o span da tool aparecer como filho do span da requisição". **Isso não corresponde à arquitetura real do repositório**: não existe uma chamada HTTP entre a API e um servidor MCP separado — `graph/nodes.py` importa e chama as funções das tools (`search_code`/`fetch_history`/`publish_comment`) diretamente, no mesmo processo; `mcp_server/server.py` expõe essas mesmas funções como tools MCP via stdio, para um client MCP externo eventual, mas o grafo não passa por ele.

A chamada HTTP que de fato existe é a saída de cada tool para a API do GitHub (`httpx.Client`/`httpx.post` em `search_code.py`/`fetch_history.py`/`publish_comment.py`). É essa chamada que foi instrumentada com `traceparent`: o span da tool (o span do node que a invoca, já que não há um span de tool separado no processo único atual) propaga contexto para a chamada de rede real. Isso mantém o mecanismo pronto e testado (`tests/unit/test_http_tracing.py`) para o dia em que um servidor MCP real sobre HTTP existir — só trocaria o destino da injeção, não a técnica.

## Testado no navegador com Ollama real

Rodado o fluxo completo (submissão → escalação → aprovação pendente) via Browser pane após a mudança de topologia do grafo (novo node `budget_gate` entre o fan-in de evidência e `analyze_impact`): parecer renderizado normalmente, `risco: Baixo`, decisão `ESCALATED` gravada na auditoria sem os campos de orçamento (comportamento correto — orçamento não estourou). Nenhum erro no console. Confirma que a topologia nova não quebra o caminho normal (orçamento padrão de 12 passos/60s nunca é atingido numa execução real de ponta a ponta).

## Testes

Novos: `tests/unit/test_budget.py`, `tests/unit/test_tracing.py`, `tests/unit/test_http_tracing.py`, `tests/unit/test_decide_autonomy_budget.py`, `tests/integration/test_scenario_5_budget_exceeded.py` (cenário 5 do PRD — `max_steps=0` força o estouro determinística e instantaneamente, sem depender de mocks lentos e frágeis em CI), além de extensões em `tests/unit/test_state.py`/`test_audit.py`.

`pytest -q`: 229 passed (26 novos), 3 skipped (Ollama real), 99,17% de cobertura. `ruff check .`/`ruff format --check .`: sem apontamentos.
