# Card 29 — Workflow n8n

**Branch/PR:** `feature/n8n-workflow`
**Resultado esperado (Kanban):** Gatilho e notificação → Card no Discord

## O que foi implementado

- `docs/lowcode/workflow-n8n.json` — workflow exportável do n8n, 5 nodes: `GitHub Webhook` (recebe o evento `issues`) → `Label é analise-impacto?` (`IF`, filtra pelo label, RF-01.3) → `POST /analyze` (`HTTP Request` para a aplicação) → `Discord` (card com resumo do parecer e link do painel de aprovação); ramo negativo do `IF` vai para um `NoOp` (`Ignorar`).
- `docker-compose.yml` ganhou o serviço `n8n` (imagem oficial `n8nio/n8n`), repassando `RADAR_API_URL`/`RADAR_APPROVAL_URL`/`DISCORD_WEBHOOK_URL` do `.env`.
- README ganhou a seção "Automação low-code (n8n)" com o passo a passo de reprodução: subir o container, importar o JSON, configurar o webhook do Discord e do GitHub, ativar o workflow.
- `.env.example` ganhou as três variáveis novas (`DISCORD_WEBHOOK_URL` vazia — nunca versionada com valor real).

## Divisão de responsabilidade (exigida pela seção 17 do PRD)

Nenhum node do workflow decide nada sobre risco, confiança ou aprovação — o `IF` só filtra pelo label (é roteamento do gatilho, não lógica de negócio), e o `HTTP Request` só repassa o payload para a aplicação, que devolve o parecer já classificado. O `Discord` só formata o que a aplicação respondeu. Documentado explicitamente nas notas (`notes`) dos nodes do próprio JSON, não só no README — para sobreviver a quem só abrir o workflow no n8n sem ler a documentação externa.

## Limitações honestamente registradas (não escondidas)

1. **`POST /analyze` aponta para um endpoint que ainda não existe** — a API é o card 30, ainda não implementado. O workflow está completo e correto na forma, mas o teste end-to-end real (Issue criada → card no Discord) só é possível depois que o card 30 existir. Isso é coerente com a ordem dos cards do Kanban, não uma omissão.
2. **Não foi possível testar a subida do container `n8n` neste ambiente de desenvolvimento** — Docker não está disponível aqui (mesma limitação já registrada no card 25 para `docker build`, lá contornada validando via CI real; aqui não há CI equivalente para importar/rodar um workflow do n8n). O JSON foi validado sintaticamente (`json.load` sem erro, estrutura de nodes/connections conferida manualmente contra o formato de exportação conhecido do n8n), mas não foi importado numa instância real do n8n.
3. **Nenhum webhook real do Discord foi criado nem usado** — criar um webhook exigiria um servidor Discord real (do usuário), e usar credenciais/URLs de webhook de terceiros sem essa configuração explícita do usuário está fora do que esta sessão deveria fazer sozinha. A variável fica documentada e vazia em `.env.example`; a instrução de como o usuário cria a própria fica no README.

## Testes

Nenhuma mudança em código Python neste card — `pytest -q`: 189 passed, 3 skipped (Ollama real), 99,09% de cobertura, sem alteração. `ruff check .`/`ruff format --check .`: sem apontamentos. `docker-compose.yml` validado com `yaml.safe_load` (sintaxe correta); `workflow-n8n.json` validado com `json.load` (JSON bem formado).

## Decisões técnicas

- `IF` node em vez de filtrar só no lado do GitHub (webhook configurado para disparar só em Issues com o label) — o webhook do GitHub para o evento `issues` não tem como filtrar por label na origem; ele dispara para toda mudança de Issue (abertura, label, fechamento, etc.), então o filtro por `action == "labeled" && label.name == "analise-impacto"` precisa acontecer no primeiro node depois do webhook, antes de qualquer chamada à aplicação.
- Ramo negativo do `IF` termina num `NoOp` explícito, não é deixado sem conexão — deixa claro no próprio workflow que o "não fazer nada" é uma decisão modelada, não uma branch esquecida.
