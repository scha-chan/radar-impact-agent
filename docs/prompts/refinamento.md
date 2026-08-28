# Refinamento de prompt — ciclo documentado (card 32)

Um ciclo real de refinamento, do prompt `03-analyze-impact` (node `analyze_impact`,
RF-04). Formato: problema observado → alteração aplicada → resultado antes/depois →
como foi medido. A seção 18 do PRD aponta este caso como o candidato natural.

## Problema observado

A primeira versão do prompt pedia, para cada impacto, um objeto com `area`,
`description`, `severity` e `evidence`. O campo `evidence` era só mais um campo
de texto — **nada obrigava o modelo a apontar uma fonte real**.

Rodando contra o `mistral` local, o `analyze_impact` produzia impactos
plausíveis mas sem lastro:

```json
{
  "impacts": [
    {"area": "listagem", "description": "A query de pedidos ganha um filtro por data",
     "evidence": "src/orders/orders_repository.py:12"},
    {"area": "performance", "description": "Filtro sem índice pode degradar a listagem",
     "evidence": "boa prática de banco de dados"},
    {"area": "manutenibilidade", "description": "Novo parâmetro aumenta a superfície da API",
     "evidence": "princípio de design de APIs"}
  ]
}
```

Dois dos três impactos citam "evidência" que não existe no material coletado —
são o modelo raciocinando por conta própria. Isso viola a **RF-04.5**
("nenhuma afirmação do parecer pode existir sem entrada correspondente em
`evidence_sources`") e torna o parecer não-auditável: quem revisa não consegue
puxar a linha até o código.

## Alteração aplicada (card 44)

Duas mudanças, deliberadamente em camadas diferentes — a instrução no prompt
reduz o ruído, mas a garantia é no código:

1. **No prompt** (`ANALYZE_IMPACT_SYSTEM`, `src/graph/prompts.py`):

   > O campo `evidence` DEVE citar textualmente um `arquivo`, `fonte` ou `ref`
   > que apareça no bloco de evidência abaixo. Se você não tem evidência no
   > bloco para sustentar um impacto, não o inclua.

2. **No node** (`analyze_impact` / `_impact_is_grounded`, `src/graph/nodes.py`):
   - se `evidence_sources` está vazio, a saída é vazia — o modelo nem é chamado;
   - todo impacto cujo `evidence` não referencia (substring, nos dois sentidos)
     um identificador de fonte coletada — caminho do arquivo, seu basename, o
     `source` do RAG, o `ref` do histórico ou o token `revisor` (card 47) — é
     **descartado**, com `analyze_impact_dropped_ungrounded_impacts` no log.

A escolha de não confiar só no prompt é a mesma da seção 13 do PRD: um modelo
local pequeno ignora instrução com frequência; a filtragem determinística é o
que efetivamente sustenta a RF-04.5.

## Resultado — antes e depois

Mesmo requisito, mesma evidência coletada (`src/orders/orders_repository.py:12`
via `search_code`; um padrão de `knowledge/listagem.md`; um PR do histórico):

| | Antes | Depois |
|---|---|---|
| Impactos gerados pelo LLM | 3 | 2–3 (varia) |
| Impactos **publicados** | 3 (2 sem lastro) | só os que citam uma fonte coletada |
| `evidence` rastreável até `evidence_sources` | ~1/3 | 100% (por construção) |
| Comportamento sem evidência nenhuma | inventava impactos | devolve vazio → escala como "não avaliado" (card 46) |

Exemplo real da execução de smoke com `mistral` (card 44), requisito de 2FA
com evidência só de RAG:

```
impacts: 2
  - autenticacao        MEDIUM  | knowledge/login.md#2fa
  - recuperacao-de-senha MEDIUM | knowledge/login.md#2fa
```

Os dois impactos apontam a fonte que os sustenta; nenhum "boa prática" solto.

## Como foi medido

- **Testes** (`tests/unit/test_analyze_impact.py`): casos dedicados — impacto
  com `evidence` vazio é descartado; impacto citando fonte inexistente é
  descartado; o impacto grounded é mantido; `evidence_sources` vazio → saída
  vazia e o modelo não é chamado.
- **Cobertura de prompt** (`tests/unit/test_prompts.py`): o builder insere cada
  peça de evidência com seu identificador citável, e a instrução de exigência
  aparece no texto do sistema.
- **Smoke com Ollama real** (`RUN_OLLAMA_TESTS=1`): a saída acima, reproduzível.
- **Golden set / LLM-as-judge** (card 39): o juiz penaliza afirmação sem
  evidência; o corte no node remove essa classe de erro antes da avaliação.
