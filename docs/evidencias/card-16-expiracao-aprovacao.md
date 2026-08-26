# Card 16 — Implementar expiração de aprovação

**Branch/PR:** `feature/approval-expiration`
**Resultado esperado (Kanban):** Evitar publicação tardia → Retoma e arquiva no TTL

## O que foi implementado

- `src/graph/nodes.py::decide_autonomy` (RF-06) agora também grava `approval_expires_at` (`datetime.now(UTC) + APPROVAL_TTL_HOURS`) sempre que escala para revisão humana. É o único lugar certo para isso: `human_approval` pausa via `interrupt()`, que nunca retorna nada na primeira passada, então não tem como persistir um campo do state antes de congelar; `decide_autonomy` roda normalmente antes da pausa, e seu retorno já é gravado pelo checkpointer.
- `src/graph/nodes.py::human_approval` (RF-07.1, card 15) ganhou uma segunda guarda, `_is_approval_expired(state)`, checada **antes** de chamar `interrupt()`. Isso cobre os dois casos de RF-07.4:
  - uma aprovação que chega **depois** do prazo: a re-execução do node bate na checagem de expiração antes de sequer chamar `interrupt()`, então o valor do resume (`"APPROVED"` ou qualquer outro) é descartado;
  - uma retomada sem decisão nenhuma (ex.: uma varredura periódica, fora do escopo deste card) também arquiva, pelo mesmo motivo.
- `APPROVAL_TTL_HOURS` (já existia em `.env.example` desde o card inicial) agora tem efeito real: `src/graph/nodes.py::APPROVAL_TTL_HOURS = int(os.getenv("APPROVAL_TTL_HOURS", "24"))`.

## Decisão: expiração vira `approval_decision = "REJECTED"`

`ApprovalDecision` (seção 8 do PRD) é fixo em `Literal["APPROVED", "REJECTED"]` — não é um campo aberto para acrescentar um terceiro valor `"EXPIRED"` sem alterar o contrato do `AgentState` documentado no PRD. `route_after_approval` já trata qualquer coisa que não seja `"APPROVED"` como arquivamento, então mapear expiração para `"REJECTED"` reaproveita esse roteamento sem mudança de contrato.

**Trade-off aceito:** isso funde, na trilha de auditoria (card 20, ainda não implementado), "um humano rejeitou explicitamente" com "o prazo expirou". O log estruturado (`human_approval_expired`, `logger.warning`) registra a distinção no nível de log; se a trilha de auditoria do card 20 precisar diferenciar os dois motivos no relatório publicado, o caminho mais simples é adicionar um campo separado (`archived_reason: Literal["REJECTED", "EXPIRED"] | None`) em vez de reabrir `approval_decision` — fica anotado aqui para quando esse card for feito.

## Testes

`tests/unit/test_decide_autonomy.py` (novo) — `approval_expires_at` é gravado com o TTL correto ao escalar por confiança baixa ou por risco `CRITICAL`; não é gravado quando publica automaticamente; respeita `APPROVAL_TTL_HOURS` customizado.

`tests/integration/test_human_approval.py` (dois testes novos):

- `test_human_approval_sets_expiry_when_pausing` — o campo chega populado no resultado da pausa (prova que `decide_autonomy` → `human_approval` → checkpointer preserva o valor).
- `test_expired_approval_archives_even_when_late_decision_is_approved` — o teste central do card: pausa, usa `graph.update_state()` para simular o relógio passando do prazo (sem esperar de verdade), retoma com `Command(resume="APPROVED")` e confirma que mesmo assim `approval_decision == "REJECTED"` e nada é publicado.

`pytest -q`: 105 passed, 3 skipped (Ollama real). `ruff check`: sem apontamentos.

## Decisões técnicas

- `graph.update_state(config, {...})` para simular a passagem do tempo nos testes, em vez de `time.sleep()`/`freezegun` — é a mesma API que uma varredura periódica real usaria para forçar um estado expirado, então o teste também documenta esse mecanismo.
- A checagem de expiração vem *antes* da chamada a `interrupt()`, não depois de recebê-la — colocá-la depois permitiria que uma decisão tardia ainda fosse processada normalmente (bug: publicaria com atraso, exatamente o que RF-07.4 quer evitar).
