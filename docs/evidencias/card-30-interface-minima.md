# Card 30 — Interface mínima

**Branch/PR:** `feature/minimal-api`
**Resultado esperado (Kanban):** Submissão e aprovação → Página funcional

## O que foi implementado

- `src/api/app.py` — app FastAPI com `lifespan` construindo o grafo + checkpointer **uma vez** por processo, reutilizados por toda requisição (é o que faz `POST /approvals/{session_id}` conseguir retomar uma sessão pausada por um `POST /analyze` anterior, cards 15/16):
  - `POST /analyze` (RF-01.2) — submete um requisito em texto livre (1–8000 caracteres, RF-01.4), roda o grafo até publicar, arquivar, bloquear (cenário 3) ou pausar (cenário 2).
  - `GET /approvals` (RF-10.2) — painel de sessões aguardando aprovação.
  - `POST /approvals/{session_id}` (RF-07.2) — aprova/rejeita, retoma a execução pausada via `Command(resume=...)`.
  - `GET /audit/{session_id}` (RF-09.4) — trilha de auditoria da sessão.
  - `GET /` — serve a página única (RF-10.1/10.2/10.3).
- `src/api/schemas.py` — contratos HTTP (`AnalyzeRequest`/`AnalyzeResponse`/`ApprovalDecisionRequest`/`PendingApproval`/`AuditEntry`), separados do `AgentState` interno.
- `src/api/static/index.html` — página única, vanilla JS/fetch, sem framework nem build step: formulário de submissão, lista de aprovações pendentes com botões Aprovar/Rejeitar, e visualizador da trilha de auditoria por `session_id`.
- `src/observability/audit.py` ganhou `read_all_entries()` (leitura sem filtro) e `list_pending_sessions()` — deriva o painel de pendências da trilha de auditoria já existente (card 20): a última decisão de uma sessão sendo `ESCALATED` (sem uma resolução depois) é o que a torna "pendente". Evita manter um registro de pendências separado e potencialmente dessincronizado da trilha real.
- `requirements.txt` ganhou `fastapi`/`uvicorn` (já resolvidos transitivamente no ambiente; travados na versão instalada).
- `tests/e2e/test_api.py` (novo, 12 testes) — aceitação via `TestClient` do FastAPI (seção 15 do PRD): publicação automática, bloqueio adversarial, escalação aparecendo no painel, fluxo completo de aprovação e de rejeição, 404 para sessão desconhecida/já resolvida, trilha de auditoria. **Fecha a lacuna que os cards 23 e 29 deixaram explicitamente registrada** — a API não existia até agora.

## Por que o painel de pendências deriva da auditoria, não de um registro à parte

Uma alternativa mais óbvia seria manter um dicionário/tabela "sessões pendentes" atualizado pelos nodes do grafo. Isso criaria uma segunda fonte de verdade que precisaria ficar sincronizada com a trilha de auditoria (card 20) em todo caminho de código — e-se um bug dessincronizar as duas, o painel mentiria sobre o que realmente aconteceu. Como a trilha de auditoria já registra exatamente `ESCALATED` (quando pausa) e a resolução correspondente depois (`APPROVED_PUBLISHED`/`REJECTED_ARCHIVED`/`EXPIRED_ARCHIVED`/`PUBLISH_DENIED`), o painel de pendências é uma **derivação**, não um estado próprio — não tem como ficar inconsistente com o que a auditoria diz.

## 404 sem distinguir "sessão desconhecida" de "já resolvida"

`graph.get_state(config)` devolve `next=()` tanto para uma thread nunca vista quanto para uma já finalizada — não há como diferenciar sem consultar a trilha de auditoria à parte. Optei por um único 404 com mensagem que cobre os dois casos, em vez de uma consulta extra só para uma mensagem de erro mais específica; documentado explicitamente no docstring do endpoint.

## Testes

`tests/e2e/test_api.py` — 12 testes cobrindo os quatro cenários relevantes à API (publicação automática, bloqueio, escalação, aprovação/rejeição), validação de entrada (RF-01.4), e os dois endpoints de leitura (`/approvals`, `/audit/{id}`) com seus casos de erro. `tests/unit/test_audit.py` ganhou dois testes diretos para `list_pending_sessions`.

`pytest -q`: **203 passed, 3 skipped** (Ollama real), 99,18% de cobertura — `src/api/app.py` e `src/api/schemas.py` em 100%. `ruff check .`/`ruff format --check .`: sem apontamentos.

## Dockerfile/`docker-compose.yml` atualizados

O `CMD` do `Dockerfile` mudou do servidor MCP (stdio, não faz sentido como processo de longa duração de um container) para `uvicorn src.api.app:app`. Isso tornou real uma limitação que o card 26 tinha registrado como hipotética: "quando a API existir e precisar escrever em volumes montados, será preciso ajustar a propriedade do diretório" — o `lifespan` da API cria o checkpoint sqlite na inicialização. Corrigido agora: `mkdir -p /app/data && chown -R radar:radar /app` antes do `USER radar` no `Dockerfile`, para o usuário sem privilégios (card 26) conseguir escrever no volume montado mesmo quando o Docker cria o volume nomeado com dono `root` por padrão. `docker-compose.yml` expõe a porta `8000` do serviço `radar`, e `RADAR_API_URL` do `n8n` (card 29) já apontava para `http://radar:8000` — a partir deste card, esse endereço responde de verdade.

## Decisões técnicas

- Página única servida como arquivo estático (`FileResponse`), sem Jinja2/template engine — não há dado dinâmico para renderizar no HTML em si (tudo vem via `fetch` depois que a página carrega), então um template engine seria complexidade sem benefício.
- `lifespan` (não `@app.on_event`, depreciado) para construir o grafo/checkpointer uma vez — padrão atual recomendado pelo FastAPI, e fecha a conexão sqlite corretamente no shutdown.
- Linguagem do requisito (RF-01.4, "fora dos idiomas suportados") não validada — exigiria detecção de idioma (dependência nova ou chamada de LLM extra só para isso); o comprimento (1–8000 chars) já é validado via Pydantic. Simplificação documentada aqui, não escondida.
