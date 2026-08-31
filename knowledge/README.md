# Corpus de padrões de impacto

Base de conhecimento usada pelo RAG (`retrieve_rag`, RF-03.2) para recuperar padrões de impacto conhecidos por tipo de feature. Reaproveita e amplia os templates de tipos de feature do mini-projeto (seção 6 do PRD) — deixam de ser respostas fixas de chat e passam a ser conhecimento recuperável por similaridade semântica.

## Origem

Conteúdo curado a partir de conhecimento geral de engenharia de software sobre impacto e risco por categoria de funcionalidade — não extraído de nenhuma fonte externa específica. Cobre os 9 tipos de feature concretos do schema `FeatureType` (`src/graph/state.py`); `outro` fica de fora de propósito, é o catch-all para requisitos que não se encaixam nos demais, e a fórmula de confiança (seção 11 do PRD) já penaliza esse caso independente do RAG.

## Estrutura de um arquivo

Um arquivo por tipo de feature (`login.md`, `cadastro.md`, ...). Dentro de cada um, uma seção `##` por padrão de impacto — a unidade que o card 13 (ingestão/chunking) vai transformar em um chunk do índice vetorial. Cada padrão segue o mesmo schema, para a recuperação retornar conteúdo comparável entre tipos de feature diferentes:

```markdown
## <nome do padrão>

**Área:** <área do sistema afetada>
**Descrição:** <o que esse padrão de impacto cobre>
**Riscos típicos:** <riscos comumente associados>
**Dependências comuns:** <o que costuma ser afetado/depender disso>
**Testes recomendados:** <cenários de teste que esse padrão sugere>
```

## Inventário

| Arquivo | Padrões (chunks) |
|---|---|
| `login.md` | 6 |
| `cadastro.md` | 6 |
| `formulario.md` | 6 |
| `api.md` | 6 |
| `upload.md` | 6 |
| `dashboard.md` | 6 |
| `listagem.md` | 6 |
| `notificacao.md` | 6 |
| `integracao.md` | 6 |
| **Total** | **54** |

Meta do card 12 (seção 21 do PRD): 50+ chunks — atingida.
