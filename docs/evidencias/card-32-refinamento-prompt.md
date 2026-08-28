# Card 32 — Documentar refinamento de prompt

**Branch/PR:** `docs/readme-reorg-card32` → PR para `develop`
**Resultado esperado (Kanban):** análise crítica de um ciclo de refinamento (problema → alteração → antes/depois → medição).

## O que foi feito

- **[`docs/prompts/refinamento.md`](../prompts/refinamento.md)** (novo) — o ciclo do prompt `03-analyze-impact`: a primeira versão produzia impactos genéricos com "evidência" inventada ("boa prática de banco de dados"), violando a RF-04.5. A correção foi em duas camadas — a instrução no prompt (`evidence` DEVE citar uma fonte do bloco) **e** o corte no node (`_impact_is_grounded` descarta o que não casa; `evidence_sources` vazio → saída vazia). Com o antes/depois em JSON, o exemplo real da execução de smoke com `mistral`, e como foi medido (testes unitários, `test_prompts.py`, smoke com Ollama, LLM-as-judge do card 39).
- **README** — a seção "Prompts e refinamento" deixou de marcar o card como pendente e passou a linkar o `refinamento.md` com o resumo do ciclo.

Este é o mesmo candidato que a seção 18 do PRD ("Ciclo de refinamento a documentar") já apontava, então não houve invenção de conteúdo — o refinamento aconteceu de fato no card 44.

## Junto neste PR (reorganização do README pedida pelo usuário)

- **Menu** substituiu o "Sumário" plano por um índice em três blocos (Entender / Rodar / Avaliar) com links para as subseções.
- **Fluxo do grafo** — o ASCII de ~55 linhas (desatualizado: sem `budget_gate`, `brief_escalation`, ciclo de reanálise) virou um diagrama **Mermaid** fiel ao `src/graph/build.py` atual.
- **"Componentes internos"** (nova seção) — `Observabilidade`, `Orçamento de execução`, `Servidor MCP` e `Automação low-code (n8n)` saíram de "Instalação e execução" (onde não eram setup) para uma seção própria de "como funciona por dentro".
- **"Segurança e limites de autonomia"** — de uma lista de parágrafos em negrito para quatro subseções (`### Contra conteúdo externo`, `### Ação irreversível`, `### Humano no circuito` — com tabela —, `### Segredos e publicação`), com prosa mais enxuta.
- **Cenários de uso** — adicionada a linha do cenário 5 (orçamento estourado, card 35), que já tinha teste.

## Verificação

Só docs — nenhuma mudança de código. `python -m pytest -q`: **392 passed, 6 skipped** (inalterado). `ruff`: não se aplica a `.md`. Os `#anchor` do Menu conferem com os slugs que o GitHub gera para cada heading; os links internos existentes (`#observabilidade-...`, `#orçamento-de-execução-...`) continuam válidos porque os headings não mudaram de texto.
