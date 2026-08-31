# Card 18 — Implementar detector adversarial

**Branch/PR:** `feature/adversarial-detector`
**Resultado esperado (Kanban):** Bloquear instrução embutida → Cenário 3 reproduzível

## O que foi implementado

- `src/governance/adversarial.py` (novo) — `detect_by_pattern(text)`: camada 1, determinística, regex sobre imperativos dirigidos ao agente, tentativas de redefinir regras e pedidos de forçar classificação/aprovação (pt e en, RF-01.1). `AdversarialVerdict` (Pydantic): schema da camada 2, saída estruturada do LLM. `render_block_message(reason)`: formata a mensagem no padrão exato do cenário 3 (seção 12 do PRD).
- `src/graph/prompts.py` ganhou `GUARD_ADVERSARIAL_SYSTEM`/`build_guard_adversarial_prompt` — documentado em `docs/prompts/02-guard-adversarial.md`, seguindo o padrão já estabelecido pelo prompt 01.
- `src/graph/nodes.py::guard_adversarial` deixou de ser stub: roda a camada 1 primeiro (sem custo); só chama o LLM (camada 2) se a camada 1 não encontrar nada. Camada 3 (contenção arquitetural) não precisou de nenhuma mudança — já é garantida desde os cards 02/04 (`score_risk` é Python puro).
- `src/graph/nodes.py::block` passa a logar a mensagem formatada (`adversarial_blocked`) — nenhuma tool de escrita é chamada a partir daqui, o roteamento condicional já existia (card 04) e desvia direto para `END`.

## Bug pego pelos próprios testes: colisão de chave no log

A primeira versão de `block` passava `extra={"message": ...}` para `logger.warning()` — `"message"` é um atributo reservado de `LogRecord`, e o logging estourava `KeyError: "Attempt to overwrite 'message' in LogRecord"` sempre que o node rodava. `tests/integration/test_scenario_3_adversarial.py` (que invoca o grafo real, não mocka logging) pegou isso na primeira execução; renomeado para `"block_message"`.

## Testes

`tests/unit/test_adversarial.py` (novo) — 9 frases adversariais conhecidas (pt/en) todas detectadas pela camada 1; 5 requisitos legítimos que mencionam termos como "segurança"/"acesso"/"risco" não geram falso positivo; case-insensitive; formato exato de `render_block_message`.

`tests/integration/test_scenario_3_adversarial.py` (novo):

- Reproduz o cenário 3 do PRD literalmente (mesmo texto da Issue #43 do exemplo) via `build_graph().invoke()` — confirma `is_adversarial=True`, nenhuma chamada a `_publish_comment`, `published_comment_url` continua `None`, e os campos que dependeriam de `score_risk`/`decide_autonomy` (nunca alcançados) continuam nos defaults de `create_initial_state`.
- Um segundo cenário com um texto que a camada 1 **não** pega, só a camada 2 (LLM mockado retornando `AdversarialVerdict(is_adversarial=True, ...)`) — prova que as duas camadas realmente compõem, não só a primeira.
- Fail-open: LLM indisponível → `is_adversarial=False` (comportamento documentado, não acidental).
- A camada 2 nunca é chamada quando a camada 1 já decidiu (mock de `build_chat_model` que registra chamada — lista continua vazia).
- A camada 2, quando chamada, pede exatamente o schema `AdversarialVerdict` a `with_structured_output` (`assert_called_once_with`).

## Refatoração colateral: `tests/helpers.py`

Adicionar uma segunda chamada a `build_chat_model().with_structured_output(...)` (agora `guard_adversarial` também usa, além de `extract_requirement`) quebrou **todos** os testes de integração que mockavam o LLM com um único `MagicMock` ingênuo — o mock devolvia o mesmo objeto (`Requirement`) para os dois schemas pedidos, e `guard_adversarial` tentava acessar `.is_adversarial` num `Requirement`, que não tem esse campo.

Corrigido centralizando o mock em `tests/helpers.py::mock_llm`, que decide o que devolver com base no schema pedido (`Requirement` vs `AdversarialVerdict`) via `side_effect`. `tests/integration/test_graph.py`, `test_evidence_parallelism.py`, `test_human_approval.py`, `test_scenario_1_happy_path.py` e `test_scenario_4_resilience.py` foram atualizados para usar o helper compartilhado em vez de montar o `MagicMock` cada um à sua maneira — reduz duplicação e evita a próxima integração quebrar os mocks de novo por engano.

`pytest -q`: 122 passed, 3 skipped (Ollama real). `ruff check`: sem apontamentos.

## Decisões técnicas

- Camada 1 sempre roda antes da camada 2 — não só por custo (evita uma chamada de LLM para casos óbvios), mas porque um padrão conhecido é uma garantia mais forte que uma inferência de modelo: não pode ser "convencido" a discordar.
- `AdversarialVerdict` fica em `governance/adversarial.py`, não em `graph/state.py` — não é um campo do `AgentState` documentado na seção 8 do PRD, é só o contrato de saída de uma chamada de LLM interna ao node, mesmo raciocínio de `Requirement` ficar em `graph/state.py` (esse sim documentado no PRD) enquanto o veredito adversarial não é.
