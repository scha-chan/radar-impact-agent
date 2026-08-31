# Card 15 — Implementar escalação humana

**Branch/PR:** `feature/human-approval`
**Resultado esperado (Kanban):** Suspender e retomar → `interrupt` com checkpointer

## O que foi implementado

- `src/graph/checkpointer.py` — `build_checkpointer()`: `SqliteSaver` sobre uma conexão sqlite (`CHECKPOINT_DB_PATH`, default `radar_checkpoints.db` — já coberto por `*.db` no `.gitignore`), com `check_same_thread=False` porque a submissão do requisito e a decisão de aprovação chegam em requisições diferentes do FastAPI (card 30), logo threads diferentes.
- `src/graph/build.py::build_graph` ganhou o parâmetro `checkpointer` (default `None`), passado para `graph.compile(checkpointer=...)`.
- `src/graph/nodes.py::human_approval` deixou de ser stub: chama `interrupt()` do LangGraph (RF-07.1) quando `approval_decision` ainda não veio preenchida, suspendendo a execução — `graph.invoke()` retorna imediatamente com a chave `"__interrupt__"`, e o state fica preservado no checkpointer até a retomada com `graph.invoke(Command(resume=decisao), config={"configurable": {"thread_id": session_id}})`.
- `.env.example` ganhou `CHECKPOINT_DB_PATH`; `requirements.txt` ganhou `langgraph-checkpoint-sqlite`.

## A guarda `if state["approval_decision"] is not None: return {}`

Sem essa guarda, todo *resume* pausaria de novo: quando `Command(resume=...)` é enviado, o LangGraph reexecuta o node `human_approval` do início — só que `interrupt()`, ao ser chamado de novo, devolve o valor do resume em vez de pausar (é assim que o mecanismo funciona). Mas nesse momento, antes do node retornar, `approval_decision` no state ainda é `None` (a atualização só é aplicada quando o node completa) — então a guarda checa o state **de entrada**, não o valor de retorno, e não interfere no resume.

O efeito colateral bom dessa guarda é retrocompatibilidade total: os testes de topologia já existentes (`test_graph.py`) que pré-preenchem `approval_decision` diretamente no state e chamam `graph.invoke(state)` **sem checkpointer nenhum** continuam funcionando sem alteração — eles simulam o que uma retomada real produziria, sem precisar montar o mecanismo de `interrupt`/`Command` inteiro. Isso está documentado nos comentários atualizados desses testes.

## Testes

`tests/integration/test_human_approval.py` (novo):

- `test_human_approval_pauses_the_graph_when_confidence_is_low` — grafo com checkpointer, confiança baixa → `"__interrupt__"` no resultado, `graph.get_state(config).next == ("human_approval",)`.
- `test_human_approval_resumes_and_publishes_on_approval` — `Command(resume="APPROVED")` após a pausa → `approval_decision="APPROVED"`, comentário publicado (arquivo, sem `issue_number`).
- `test_human_approval_resumes_and_archives_on_rejection` — `Command(resume="REJECTED")` → arquivado, nada publicado.
- `test_checkpointer_persists_state_across_reconnection` — a prova real de RF-07.1: fecha a conexão sqlite depois de pausar (simulando o servidor reiniciando) e retoma com uma **conexão nova para o mesmo arquivo**. Sem esse teste, `SqliteSaver` não se distinguiria de um checkpointer em memória — é o teste que justifica a escolha de persistência em disco em vez de `InMemorySaver`.

`tests/integration/test_graph.py` (ajustado): o teste de baixa confiança agora assere `"__interrupt__" in result` (antes só conferia `published_comment_url is None`, que continuava `True` só porque o node nunca era alcançado — agora é `True` porque o grafo realmente pausou). Comentários de dois testes atualizados para não referenciar mais "interrupt real do card 15" como algo futuro.

`pytest -q`: 99 passed, 3 skipped (Ollama real). `ruff check`: sem apontamentos.

## Decisões técnicas

- `SqliteSaver(conn)` em vez de `SqliteSaver.from_conn_string(path)` — o construtor por `conn_string` da biblioteca é um *context manager* que fecha a conexão ao sair do `with`, incompatível com um servidor de vida longa onde a conexão precisa ficar aberta entre a pausa (uma requisição) e a retomada (outra requisição, minutos ou horas depois). O construtor direto por `sqlite3.Connection` evita esse problema.
- `checkpointer=None` como default de `build_graph()` — mantém todos os testes existentes que não precisam de HITL de verdade (a maioria) livres de configurar um checkpointer só para compilar o grafo.
- RF-07.2 (endpoints `GET /approvals` / `POST /approvals/{session_id}`) e RF-07.3 (notificação via n8n) ficam para os cards 29/30 — este card cobre exatamente o que o Kanban pede: "interrupt com checkpointer". A retomada é simulada nos testes diretamente com `Command(resume=...)`, que é o mecanismo que a rota `POST /approvals/{session_id}` vai chamar por baixo.
