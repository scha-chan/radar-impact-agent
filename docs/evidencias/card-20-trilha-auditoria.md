# Card 20 — Trilha de auditoria

**Branch/PR:** `feature/audit-trail`
**Resultado esperado (Kanban):** Segundo sinal → JSONL correlacionado

## O que foi implementado

- `src/observability/audit.py` (novo) — `AuditRecord` (dataclass) e `record_audit()`/`read_audit_trail()`: append de uma linha JSON em `AUDIT_LOG_PATH` (default `audit/trail.jsonl`, já coberto por `.gitignore`) por decisão de autonomia; leitura filtrando por `session_id`, na ordem em que foram gravadas — a base para a reconstrução de uma execução real (card 21) e para `GET /audit/{session_id}` (RF-09.4, card 30).
- Quatro pontos de decisão instrumentados em `src/graph/nodes.py`:
  - `decide_autonomy` → `ESCALATED` quando escala (não grava nada quando publica sozinho — só vira decisão de fato depois que a publicação acontece, ver abaixo).
  - `block` → `BLOCKED_ADVERSARIAL`, com o `adversarial_reason` (card 18) como `reason`.
  - `publish_comment` → `AUTO_PUBLISHED` (sistema sozinho) ou `APPROVED_PUBLISHED` (humano aprovou antes, cards 15/16), só depois que a tool de fato roda; `PUBLISH_DENIED` se o `ToolExecutor` (card 17) recusar — não deveria acontecer em operação normal, mas fica registrado se acontecer.
  - `archive` → `REJECTED_ARCHIVED` ou `EXPIRED_ARCHIVED`.

## Distinguir rejeição humana de expiração sem mudar o contrato do `AgentState`

O card 16 documentou o trade-off: expiração de TTL vira `approval_decision="REJECTED"` porque `ApprovalDecision` é um `Literal` fechado no PRD (seção 8), sem um terceiro valor `"EXPIRED"`. Isso significa que `archive` não pode simplesmente olhar `approval_decision` para saber qual dos dois aconteceu.

A solução: reavaliar `approval_expires_at` contra o relógio atual no próprio `archive`. Isso funciona porque `human_approval` (card 16) nunca deixa uma decisão humana tardia chegar até `archive` depois do prazo — a checagem de expiração acontece **antes** de `interrupt()` retornar o valor do resume. Então, se `approval_expires_at` já passou no momento em que `archive` roda, só pode ter sido o próprio sistema quem forçou `REJECTED` por TTL — nunca um humano rejeitando dentro do prazo. Não há caso em que essa inferência dê falso positivo.

## Testes

`tests/unit/test_audit.py` (novo) — `record_audit`/`read_audit_trail` isolados: grava linha JSON válida, cria diretório pai, faz append sem truncar, inclui `reason` só quando presente, filtra por `session_id` preservando ordem, lida com arquivo inexistente e sessão desconhecida.

`tests/integration/test_audit_trail.py` (novo) — cada um dos quatro pontos de decisão testado isoladamente chamando o node direto (sem precisar rodar o grafo inteiro): `ESCALATED` grava (e não escalar não grava nada), `BLOCKED_ADVERSARIAL` carrega o motivo, `AUTO_PUBLISHED`/`APPROVED_PUBLISHED`/`PUBLISH_DENIED` cobrem os três desfechos de `publish_comment`, `REJECTED_ARCHIVED`/`EXPIRED_ARCHIVED` cobrem os dois desfechos de `archive` (incluindo o caso de nunca ter escalado, `approval_expires_at=None`). Um teste final roda o grafo real de ponta a ponta e confirma a correlação: duas entradas (`ESCALATED`, `REJECTED_ARCHIVED`) com o mesmo `session_id`.

## Achado durante a implementação: isolamento de `cwd` nos testes

Antes deste card, nenhum teste de integração precisava se preocupar com o diretório de trabalho além de `publish_comment` (dry-run). A partir de agora, **quatro** nodes gravam arquivo a cada execução real do grafo — testes que invocam `build_graph().invoke()` sem isolar o `cwd` passariam a escrever `audit/trail.jsonl` dentro do próprio repositório a cada rodada de teste.

Corrigido com um fixture `autouse=True` em `tests/conftest.py` (novo) que isola o `cwd` de **todo** teste num `tmp_path` descartável — mais robusto que adicionar `monkeypatch.chdir(tmp_path)` manualmente em cada teste que passasse a tocar o disco (e também protege os cards futuros que ainda vão gravar arquivo: card 21 lê a trilha, card 30 expõe os endpoints). Testes que já pediam `tmp_path` diretamente continuam funcionando sem alteração — é o mesmo fixture, `function`-scoped, cacheado por teste.

`pytest -q`: 145 passed, 3 skipped (Ollama real). `ruff check`: sem apontamentos.

## Decisões técnicas

- `decide_autonomy` só grava `ESCALATED`; `AUTO_PUBLISHED` fica em `publish_comment` — evita registrar uma decisão que ainda pode não se concretizar (a autorização em `publish_comment` ainda pode falhar, `PUBLISH_DENIED`).
- `AuditRecord` é uma dataclass simples com `to_dict()`, não reaproveita `ImpactAnalysis`/outros modelos Pydantic do `AgentState` — o registro de auditoria é sobre a **decisão**, não sobre o parecer; tem campos e propósito diferentes (seção 14 do PRD já define o schema exato do exemplo).
- `AUDIT_LOG_PATH` como env var (mesmo padrão de `CHROMA_PERSIST_DIR`/`CHECKPOINT_DB_PATH`) — um único arquivo JSONL para todas as sessões (não um arquivo por sessão), porque `read_audit_trail` já filtra por `session_id`; um arquivo por sessão exigiria descobrir o nome do arquivo a partir do `session_id`, complexidade sem benefício aqui.
