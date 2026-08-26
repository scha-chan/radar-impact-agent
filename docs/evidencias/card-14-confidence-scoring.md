# Card 14 — Implementar confidence scoring

**Branch/PR:** `feature/confidence-scoring`
**Resultado esperado (Kanban):** Medir qualidade da evidência → Score reproduzível com testes

## Contexto: o que já existia

A fórmula pura (`calculate_confidence`, `src/domain/risk.py`) e o node que a consome (`score_risk`, `src/graph/nodes.py`) já existiam desde o **card 02** e o **card 04** — determinística, com piso 0/teto 100, e 30 testes unitários cobrindo cada dedução isoladamente (`tests/unit/test_risk.py`). Isso já satisfazia RF-05 no nível da função pura.

O que faltava — e é o objetivo real deste card, dado que os cards 8, 9 e 13 (as três fontes de evidência) só ficaram prontos depois do card 02 — era provar que o **node** `score_risk` soma corretamente os sinais de qualidade quando alimentado pela evidência **real** das três tools (não apenas com stubs vazios), e fechar uma lacuna de determinismo que essa integração mais recente abriu.

## O que foi implementado

- `tests/integration/test_scenario_1_happy_path.py` (novo) — Cenário 1 do PRD (seção 12): `search_codebase`, `retrieve_rag` e `fetch_history` mockados para retornar achados reais fazem o grafo completo produzir `confidence=100`, `risk_level=LOW`, `human_review_required=False` e publicação automática. Um segundo teste chama `nodes.score_risk` isoladamente 20 vezes com o mesmo estado de evidência e confirma que o resultado nunca varia (RF-05.3 estendido ao node, não só à função pura).
- `tests/integration/test_scenario_4_resilience.py` (corrigido) — o teste de fallback de `search_code` usava `feature_type="listagem"`, que **tem** corpus dedicado em `knowledge/`. Antes do card 13, `retrieve_rag` era stub e sempre retornava vazio, então a dedução de confiança do RAG (`-20`) era garantida. Com `retrieve_rag` real, o resultado do teste passou a depender de o Ollama local ter ou não o modelo de embedding (`OLLAMA_EMBED_MODEL`) instalado — no ambiente de desenvolvimento havia Ollama rodando mas sem esse modelo, então a chamada falhava e mascarava a mesma dedução por acidente, não por design. Corrigido mockando `nodes.retrieve_patterns` para retornar `[]` explicitamente, isolando o cenário à falha de `search_code` que ele realmente testa.

## Por que isso é "confidence scoring", não só "achar um bug de teste"

A fórmula de confiança (seção 11 do PRD) existe para medir **qualidade da evidência disponível**, não a certeza do LLM. Sem os testes de cenário 1 e a correção do cenário 4, a suíte não provava que essa medição continuava correta quando as três fontes de evidência deixaram de ser stubs — o risco real era um regressão silenciosa (ex.: `evidence_sources` contando errado, ou uma dedução deixando de disparar) passar despercebida porque os testes unitários da fórmula pura não tocam o node nem a composição com dados reais.

## Testes

- `pytest -q`: 95 passed, 3 skipped (dependentes de Ollama real) — 2 testes novos em relação ao card 13.
- `ruff check` nos arquivos novos/alterados: sem apontamentos.

## Decisões técnicas

- Os testes de cenário mockam `nodes.search_code`, `nodes.retrieve_patterns` e `nodes._fetch_history` diretamente (mesmo padrão já usado em `test_evidence_parallelism.py` e `test_scenario_4_resilience.py`) — evita qualquer dependência de rede (GitHub API, Ollama) para o resultado ser determinístico em CI.
- O cenário 1 não popula `risks`/`impacts` (isso é `analyze_impact`, ainda stub — card 14 do LLM, distinto do card 14 do Kanban) — `aggregate_risk_level([])` retorna `LOW` por decisão já documentada no card 02, então o teste reflete o comportamento real do grafo no estágio atual, não um cenário hipotético completo.
