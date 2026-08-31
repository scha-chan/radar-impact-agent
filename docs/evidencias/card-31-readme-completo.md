# Card 31 — README completo

**Branch/PR:** `docs/readme-completo`
**Resultado esperado (Kanban):** Permitir avaliar e reproduzir → Todas as seções do item 5.2

## O que foi feito

O README vinha crescendo incrementalmente card a card desde o início do projeto (cada card adicionando sua própria seção de reprodução — Observabilidade no card 21, low-code no card 29, interface mínima no card 30). Este card consolida tudo num documento único, corrige o que ficou desatualizado, e adiciona as seções que nenhum card anterior tinha motivo para criar sozinho.

### Seções novas

- **Sumário** (índice com âncoras) — o arquivo passou de ~295 para bem mais linhas; navegável do topo.
- **Cenários de uso** — os quatro cenários do PRD (seção 12), cada um linkado ao teste de integração que o reproduz de verdade.
- **Segurança e limites de autonomia** — as três camadas de defesa contra entrada adversarial (card 18), permissões de tool (cards 10/17), escalação com expiração (cards 15/16), `DRY_RUN`, e a política de segredos.
- **Estrutura do repositório** — árvore de diretórios anotada, para quem for avaliar navegar sem precisar abrir o PRD inteiro.
- **QA e qualidade** — gate de cobertura (card 22), priorização de teste, code review com IA (card 24), link para os exemplos práticos.
- **DevOps: pipeline, logs e anomalias** — CI (card 25), análise de logs (card 26), dataset e anomalia (card 27), tendência (card 28) — nenhum desses quatro cards tinha link nenhum no README antes deste card.
- **Prompts e refinamento** — tabela dos prompts documentados; refinamento (card 32) marcado como pendente, não fabricado.
- **Vídeo de demonstração** — marcado como pendente (card 33), não fabricado.
- **Limitações conhecidas e evolução futura** — adaptado da seção 25 do PRD, incluindo a nota explícita de que `analyze_impact` (classificação real de impactos/riscos) continua stub.

### Correções de conteúdo desatualizado

- A ressalva "API, servidor MCP e `docker compose up` chegam nos próximos cards" (verdadeira quando escrita, card 21) foi removida — todos os três existem desde os cards 07/25/30.
- A limitação do n8n (card 29) que dizia "`POST /analyze` chama um endpoint que ainda não existe" foi atualizada — o endpoint existe desde o card 30; a limitação real remanescente (não testável sem Docker/Discord real) continua registrada.
- Seção de instalação ganhou o passo `ollama pull nomic-embed-text` (card 13), que nunca tinha sido adicionado.
- "Rodando os testes" atualizado para refletir o gate de cobertura automático (`pyproject.toml`, card 22) em vez do comando antigo sem `--cov`.

## Por que "pendente" em vez de fabricar as seções que faltam

Os cards 32 (refinamento) e 33 (vídeo) ainda não foram feitos. Preencher essas seções com conteúdo fictício para "completar" o README seria pior do que deixá-las honestamente marcadas como pendentes — um avaliador que clicasse num link morto ou lesse uma reflexão de refinamento inventada teria motivo real de desconfiança do resto do documento. As duas seções existem como esqueleto (título, o que vai entrar, qual card completa) para o README não precisar de mais uma reestruturação quando esses cards forem feitos — só preencher.

## Testes

Nenhuma mudança de código — `pytest -q`: 203 passed, 3 skipped (Ollama real), 99,18% de cobertura, sem alteração. `ruff check .`/`ruff format --check .`: sem apontamentos. Todos os links relativos do README verificados programaticamente contra o sistema de arquivos (nenhum link quebrado).
