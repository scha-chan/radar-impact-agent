# Card 10 — Implementar `publish_comment`

**Branch/PR:** `feature/mcp-github-tools`
**Resultado esperado (Kanban):** Publica com `DRY_RUN` alternável

## O que foi implementado

- `src/governance/permissions.py` — `ToolPermission` e `authorize()`: implementação mínima do padrão da seção 13 do PRD (`Tool(name=..., permission=..., destructive=..., requires_approval_when=...)`). Escopo deste card: só o suficiente para proteger `publish_comment`; o card 17 generaliza para todas as tools (recusar chamada sem permissão declarada, não só as destrutivas)
- `src/mcp_server/tools/publish_comment.py` — `publish_comment()`: chama `authorize()` primeiro (RF-08.2/RF-08.3); se `DRY_RUN` ou sem `issue_number`, grava markdown em `audit/dry_run/{session_id}.md` (RF-08.4); senão, `POST /repos/{repo}/issues/{issue_number}/comments` na API do GitHub
- `graph/nodes.py::publish_comment` — reescrito de stub para real
- `server.py` — **decisão:** `publish_comment` não é exposta como tool MCP genérica (diferente de `search_code`/`fetch_history`) — precisa do `AgentState` inteiro para autorizar, e um client MCP externo não pode fornecer isso com a garantia de que a aprovação humana foi de fato concedida. Só o node do grafo chama

## Testes

- `tests/unit/test_permissions.py` — 5 testes: nega sem aprovação, nega se rejeitado, permite se aprovado, permite quando revisão não é exigida, ignora tools não-destrutivas
- `tests/unit/test_publish_comment.py` — 6 testes: `PermissionDeniedError` propagada, arquivo dry-run gravado com conteúdo correto, arquivo gravado mesmo sem `DRY_RUN` quando não há `issue_number`, chamada real à API mockada com `respx`, `None` em falha da API, `None` sem config
- `tests/integration/test_graph.py` — o teste do card 04 que verificava o publish via URL stub precisou de ajuste: sem `issue_number`, o comportamento real e correto é gravar arquivo, não "publicar"; rodado com `monkeypatch.chdir(tmp_path)` para não sujar o repositório com `audit/dry_run/` real durante os testes

## Por que não há smoke test contra a API real (diferente dos cards 08 e 09)

`publish_comment` sem `DRY_RUN` cria um comentário **real e público** numa Issue do GitHub — uma ação visível, irreversível e que outras pessoas veriam. Publicar conteúdo é uma ação que exige confirmação explícita a cada vez, não algo para automatizar num smoke test de desenvolvimento. A cobertura real desta tool vem de: `respx` mockando a chamada POST (comportamento de sucesso e de falha) e o teste do fluxo `DRY_RUN` real (grava arquivo de verdade em disco, sem tocar o GitHub). Se quiser ver uma publicação real acontecendo, isso deve ser pedido explicitamente, com uma Issue real preparada para o teste.

## Prompt utilizado

> "Sim, segue"

## Decisões técnicas

- **Sem retry automático na chamada POST real** — diferente de `search_code`/`fetch_history` (GET, idempotentes), reenviar um POST após timeout arrisca duplicar o comentário se a primeira tentativa tiver sucedido do lado do servidor sem a resposta voltar. Timeout de 10s ainda se aplica; só o retry fica de fora, decisão deliberada e documentada no docstring do módulo
- `render_comment()` marcado como **provisório** — compõe markdown a partir dos campos já disponíveis no state (`risk_level`, `confidence`, `requirement`), porque `ImpactAnalysis` ainda não existe (chega no card 14, junto do prompt `04-compose-report` já previsto na seção 18 do PRD)
- Sem `issue_number` (RF-01.2 permite submissão por texto livre via API, sem Issue), `publish_comment` grava em arquivo mesmo com `DRY_RUN=false` — não existe "publicar" sem uma Issue de destino; decisão não explicitada no PRD mas necessária para a tool não falhar silenciosamente nesse caso
- `authorize()` roda mesmo sabendo que a topologia do grafo (cards 04/06) já só alcança `publish_comment` em estados autorizados — defesa em profundidade contra bug de roteamento futuro ou chamada direta da tool fora do grafo
