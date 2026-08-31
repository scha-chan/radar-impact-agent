# Card 12 — Montar o corpus de padrões de impacto

**Branch/PR:** `feature/rag-padroes`
**Resultado esperado (Kanban):** `knowledge/` com 50+ chunks

## O que foi implementado

- `knowledge/README.md` — documenta origem do conteúdo, schema de cada padrão e inventário de chunks
- `knowledge/{login,cadastro,formulario,api,upload,dashboard,listagem,notificacao,integracao}.md` — 9 arquivos, um por tipo de feature concreto do schema `FeatureType`; `outro` fica de fora (é o catch-all, já penalizado pela fórmula de confiança independente do RAG)
- Cada arquivo tem 6 padrões de impacto (`##`), todos seguindo o mesmo schema: **Área**, **Descrição**, **Riscos típicos**, **Dependências comuns**, **Testes recomendados** — verificado programaticamente, os 5 campos aparecem exatamente 6 vezes em cada um dos 9 arquivos
- **54 chunks no total** (9 × 6) — acima da meta de 50+

## Por que este schema

O schema fixo por padrão não é só estético — é o que torna a recuperação semântica (card 13) comparável entre tipos de feature diferentes: um padrão de "login" e um de "upload" têm a mesma estrutura de campos, então o retriever pode devolver "riscos típicos" ou "testes recomendados" de qualquer um deles de forma consistente para `analyze_impact` (card 14) consumir.

## Prompt utilizado

> "Sim, segue"

## Decisões técnicas

- Conteúdo curado a partir de conhecimento geral de engenharia de software, não extraído de fonte externa específica — documentado explicitamente em `knowledge/README.md` para não passar a impressão de que é uma base factual citável
- 6 padrões por tipo de feature (não um número variável) — mantém a base equilibrada; um tipo de feature com muito mais chunks que os outros enviesaria a recuperação a favor dele
- `outro` sem arquivo dedicado — é o catch-all para requisitos que não se encaixam nos 9 tipos concretos; dar padrões genéricos a ele diluiria o propósito da penalização já prevista na fórmula de confiança (seção 11 do PRD, `feature_type == "outro"` → −15)
