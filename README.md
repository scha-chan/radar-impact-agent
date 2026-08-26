# RADAR — Agente de Análise de Impacto e Risco de Requisitos

> Projeto avaliativo M2.2 — IA para Desenvolvedores [T1]. Em desenvolvimento.

Especificação completa: [docs/PRD-RADAR-Agente-Impacto-Risco.md](docs/PRD-RADAR-Agente-Impacto-Risco.md)

Este README será expandido com instalação, execução, cenários de uso e evidências
conforme o desenvolvimento avança (ver seção 5.2 do PRD). As seções abaixo cobrem
descrição da solução e classificação/arquitetura.

---

## Descrição da solução

**Problema.** Times de desenvolvimento aprovam mudanças de requisito sem uma
avaliação sistemática do que elas quebram. O impacto costuma ser descoberto só
durante a implementação — ou em produção — porque a análise depende de quem
estava na reunião e de quanto contexto essa pessoa tem de memória.

**Solução.** RADAR é um agente que recebe um requisito de mudança (uma Issue do
GitHub), coleta evidência real do código e do histórico do repositório, cruza
essa evidência com uma base de padrões de impacto conhecidos, e produz um
parecer estruturado de risco. Pareceres de baixa confiança não são publicados
sem aprovação humana.

**Público.** Tech leads (decidem planejamento a partir do parecer), product
owners (entendem custo de risco de uma feature), QA leads (usam os testes
recomendados para priorizar esforço) e aprovadores técnicos (evitam que risco
alto passe silenciosamente). Detalhes de cada persona na seção 4 do PRD.

**Objetivo e valor entregue.** Tornar a análise de impacto uma etapa que
sempre acontece, é rastreável até a evidência que a sustenta, e não depende da
disponibilidade de uma pessoa específica. O valor não é substituir o
julgamento técnico, e sim garantir que ele parta de evidência real e que
mudanças de alto risco não avancem sem revisão explícita.

**Saída principal.** Objeto `ImpactAnalysis` validado por Pydantic, publicado
como comentário markdown na Issue de origem.

### Continuidade do mini-projeto

O edital permite evoluir a aplicação do mini-projeto do módulo. O RADAR reaproveita
quatro capacidades — o restante foi refatorado ou descartado porque o produto
mudou de pergunta: o agente anterior respondia *"como testar esta
funcionalidade?"*; o RADAR responde *"o que esta mudança quebra, e vale a pena
implementá-la?"*.

| Componente do mini-projeto | Destino no RADAR |
|---|---|
| Templates de tipos de feature | Refatorado → corpus RAG de padrões de impacto |
| Confidence Scoring | Mantido e ampliado → decide autonomia de publicação |
| Escalação Humana | Refatorado → `interrupt` do LangGraph |
| Audit Trail (JSONL) | Mantido → segundo sinal de observabilidade |
| Tool Permissions | Mantido → protege uma ação real e irreversível |
| Evidence Tracking | Mantido e ampliado → toda afirmação do parecer aponta sua origem |
| Geração de critérios/testes | Rebaixado → campo `recommended_tests`, consequência da análise |
| Sandbox, Token Budget, Preview, Draft | Descartados — perderam propósito sem execução de código |

Tabela completa e justificativas: seção 6 do PRD.

---

## Classificação e arquitetura

### Classificação: sistema híbrido

RADAR é classificado como **sistema híbrido**, não como agente autônomo puro
nem como workflow puramente determinístico:

- **Componente agêntico** — o LLM decide quais termos buscar no código,
  interpreta o requisito em linguagem natural, classifica impactos por área e
  redige o parecer. Essas tarefas exigem julgamento sobre texto livre e não têm
  uma regra fixa que as substitua.
- **Componente determinístico** — a matriz de risco, o cálculo de confiança, o
  threshold de escalação, a validação de permissões e o roteamento do grafo são
  regras Python puras, sem participação do modelo.

Essa separação é deliberada: **é o que impede o agente de "decidir" que um
risco alto é baixo.** O LLM opina sobre impactos; nunca decide se o parecer sai
sozinho ou se uma ação irreversível é autorizada.

### Fluxo do grafo (LangGraph)

```
                        Issue do GitHub
                              │
                              ▼
                   ┌──────────────────────┐
                   │  extract_requirement │   LLM → Pydantic
                   └──────────┬───────────┘
                              │
                              ▼
                   ┌──────────────────────┐
                   │   guard_adversarial  │   determinístico + LLM
                   └──────────┬───────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼ adversarial       ▼ ok
              ┌──────────┐              │
              │  block   │              │
              └──────────┘              │
                              ┌─────────┴─────────┬─────────────────┐
                              ▼                   ▼                 ▼
                     ┌────────────────┐  ┌────────────────┐  ┌──────────────┐
                     │ search_codebase│  │  retrieve_rag  │  │ fetch_history│
                     │  (GitHub API)  │  │   (padrões)    │  │(commits/PRs) │
                     └────────┬───────┘  └────────┬───────┘  └──────┬───────┘
                              └───────────────────┼─────────────────┘
                                                  ▼
                                      ┌───────────────────────┐
                                      │    analyze_impact     │   LLM
                                      └───────────┬───────────┘
                                                  ▼
                                      ┌───────────────────────┐
                                      │      score_risk       │   determinístico
                                      └───────────┬───────────┘
                                                  ▼
                                      ┌───────────────────────┐
                                      │   route_by_confidence │
                                      └───────────┬───────────┘
                                        ┌─────────┴─────────┐
                                        ▼                   ▼
                            confiança ≥ threshold    confiança < threshold
                                        │                   │
                                        │                   ▼
                                        │         ┌───────────────────┐
                                        │         │  human_approval   │  interrupt
                                        │         └─────────┬─────────┘
                                        │            ┌──────┴──────┐
                                        │            ▼             ▼
                                        │        aprovado      rejeitado
                                        │            │             │
                                        └────────────┤             ▼
                                                     ▼         ┌────────┐
                                          ┌────────────────┐   │ arquiva│
                                          │ publish_comment│   └────────┘
                                          │  (GitHub API)  │
                                          └────────┬───────┘
                                                   ▼
                                                  END
```

**Requisitos de modelagem do fluxo, e onde aparecem:**

| Requisito | Onde está no grafo |
|---|---|
| Execução sequencial | `extract → guard → ... → score → route` |
| Ramificação condicional | `guard_adversarial` e `route_by_confidence` |
| Paralelização | as três coletas de evidência, via `Send` API do LangGraph |
| Condição de parada | `retries_left` decrementado a cada falha de tool; `approval_expires_at` no aguardo de aprovação |

### Stack

| Camada | Tecnologia |
|---|---|
| Orquestração | LangGraph |
| API | FastAPI |
| Validação | Pydantic v2 |
| Tools | Servidor MCP próprio (Python SDK) |
| Vetorial | ChromaDB (local, persistente) |
| Persistência de estado | SqliteSaver (checkpointer LangGraph) |
| Logs | structlog (JSON) |
| Trace | OpenTelemetry (exporter console/arquivo) |
| Testes | pytest, pytest-asyncio, respx |
| Lint | ruff |
| CI | GitHub Actions |
| Low-code | n8n (Docker local) |
| Modelo | configurável por variável de ambiente (`LLM_MODEL`, `LLM_PROVIDER`) |

Detalhes completos de escopo, requisitos funcionais e cenários: seções 5, 9 e
12 do [PRD](docs/PRD-RADAR-Agente-Impacto-Risco.md).

---

## Instalação e execução

> Esta seção acompanha o desenvolvimento — reflete só o que já está implementado. Hoje isso é o grafo (com nodes stub) e a suíte de testes; API, servidor MCP e `docker compose up` chegam nos próximos cards e serão adicionados aqui quando existirem (RNF-06).

### Pré-requisitos

- Python 3.11+ (desenvolvido e testado com 3.14)
- Git

### Configuração

```bash
git clone https://github.com/scha-chan/radar-impact-agent.git
cd radar-impact-agent

python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
```

`.env` não precisa de valores reais ainda — nenhuma integração externa (LLM, GitHub) está implementada nesta etapa. Ver `.env.example` para as variáveis já previstas (seção 18 do PRD).

### Rodando os testes

```bash
python -m pytest tests/ -v
```

### Executando o grafo (stub) diretamente

Sem API ainda, o jeito de ver o grafo rodando é invocá-lo direto em Python:

```python
from src.graph.build import build_graph
from src.graph.state import create_initial_state

graph = build_graph()
state = create_initial_state("Adicionar filtro por data na listagem de pedidos")
resultado = graph.invoke(state)

print(resultado["risk_level"], resultado["confidence"], resultado["human_review_required"])
```

Com os nodes de evidência ainda stub (listas vazias), a confiança calculada fica abaixo do threshold padrão (70) e o resultado sempre escala para aprovação humana — comportamento esperado até os cards 8, 9 e 13 (busca de código, histórico e RAG) substituírem os stubs por integrações reais.
