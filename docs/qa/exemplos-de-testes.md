# Exemplos de como testar o RADAR

Guia prático para experimentar o agente manualmente, além da suíte automatizada. Todo exemplo abaixo foi **rodado de verdade** antes de entrar neste arquivo — a saída mostrada é real, não hipotética. Acompanha o desenvolvimento: cresce conforme novos nodes deixam de ser stub.

## Pré-requisitos

```bash
python -m venv venv && venv\Scripts\activate      # ou source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                              # preencher GITHUB_TOKEN/GITHUB_REPO para os exemplos com API real
ollama serve                                       # em outro terminal
ollama pull mistral
```

Detalhes completos: seção "Instalação e execução" do [README](../../README.md).

## 1. Suíte automatizada

```bash
python -m pytest tests/ -v
```

Roda 78 testes sem precisar de Ollama nem de `GITHUB_TOKEN` — tudo mockado (LLM via `unittest.mock`, GitHub via `respx`). Os três smoke tests contra serviços reais ficam de fora por padrão (`pytestmark` com `skipif`); ligar um de cada vez:

```bash
RUN_OLLAMA_TESTS=1 python -m pytest tests/integration/test_extract_requirement_ollama.py -v
RUN_GITHUB_TESTS=1 python -m pytest tests/integration/test_search_code_github.py tests/integration/test_fetch_history_github.py -v
```

Não existe smoke test automatizado para `publish_comment` sem `DRY_RUN` — publicar um comentário real numa Issue pública não é algo para automatizar (ver seção 5 abaixo, e [docs/evidencias/card-10-publish-comment.md](../evidencias/card-10-publish-comment.md)).

## 2. Rodando o grafo manualmente

Todos os exemplos abaixo partem do mesmo padrão:

```python
from src.graph.build import build_graph
from src.graph.state import create_initial_state

graph = build_graph()
state = create_initial_state("<texto do requisito>", issue_number=<opcional>)
resultado = graph.invoke(state)
```

### Exemplo 1 — fluxo principal, com API real do GitHub

```bash
python -c "
from src.graph.build import build_graph
from src.graph.state import create_initial_state

graph = build_graph()
state = create_initial_state(
    'Adicionar filtro por data na listagem de pedidos, permitindo selecionar intervalo inicial e final',
    issue_number=41,
)
r = graph.invoke(state)

print('feature_type:', r['requirement'].feature_type)
print('search_terms:', r['requirement'].search_terms)
print('code_matches:', len(r['code_matches']))
print('confidence:', r['confidence'])
print('human_review_required:', r['human_review_required'])
"
```

**Saída real:**

```
feature_type: listagem
search_terms: ['pedidos', 'filtro', 'data', 'intervalo', 'inicial', 'final']
code_matches: 0
confidence: 25
human_review_required: True
```

`feature_type` e `search_terms` vieram do LLM de verdade (Ollama/mistral). `code_matches` deu zero porque o Code Search do GitHub ainda não indexou este repositório (atraso normal — ver [docs/evidencias/card-08-search-code.md](../evidencias/card-08-search-code.md)); em consequência, a confiança calculada (25) fica abaixo do threshold padrão (70) e o resultado escala para revisão humana. Rode de novo depois de o repositório acumular histórico — o número deve subir.

### Exemplo 2 — forçar a publicação (aprovação manual) e ver o `DRY_RUN`

Sem passar por `human_approval` de verdade (isso é o card 15), dá para simular uma aprovação já concedida escrevendo direto no estado antes de invocar:

```bash
python -c "
from src.graph.build import build_graph
from src.graph.state import create_initial_state

graph = build_graph()
state = create_initial_state('Adicionar autenticacao por 2FA no login de usuarios')
state['approval_decision'] = 'APPROVED'
r = graph.invoke(state)
print('published_comment_url:', r['published_comment_url'])
"
```

**Saída real:**

```
published_comment_url: file://audit/dry_run/4d3d3a2a.md
```

Sem `issue_number`, `publish_comment` grava em arquivo mesmo com `DRY_RUN=false` (RF-08.4 — não existe "publicar" sem uma Issue de destino). Conteúdo gerado:

```markdown
## Parecer RADAR

**Nível de risco:** LOW
**Confiança:** 25
**Revisão humana necessária:** sim

**Tipo de feature identificado:** login

_session_id: 4d3d3a2a_
```

Para testar publicando de verdade numa Issue real, é preciso `issue_number` + `GITHUB_TOKEN`/`GITHUB_REPO` válidos + `DRY_RUN=false` — **peça confirmação antes de rodar isso**, é uma ação irreversível e pública.

### Exemplo 3 — simular falha de tool (retry/backoff reais)

Um `GITHUB_TOKEN` inválido faz `search_code`/`fetch_history` baterem 401 de verdade na API, disparando o retry com backoff real (não mockado):

```bash
GITHUB_TOKEN="token-invalido" GITHUB_REPO="scha-chan/radar-impact-agent" python -c "
import time
from src.graph.build import build_graph
from src.graph.state import create_initial_state

graph = build_graph()
state = create_initial_state('Adicionar exportacao de relatorio em PDF no dashboard financeiro')
start = time.time()
r = graph.invoke(state)
print('tempo:', round(time.time() - start, 1), 's')
print('tools_failed:', r['tools_failed'])
print('confidence:', r['confidence'])
"
```

**Saída real:**

```
tempo: 17.4 s
tools_failed: ['search_code', 'fetch_history']
confidence: 0
```

17.4s reais de backoff (0.5s + 1s por combinação termo/endpoint que falhou, seis combinações entre `search_code` e os dois endpoints de `fetch_history`). Confiança cai ao piso (0) — cada tool falhada deduz 15, mais as deduções por ausência de evidência. Este é o mesmo mecanismo coberto por `tests/integration/test_scenario_4_resilience.py` (card 11), só que ali mockado para não levar 17s por execução de teste.

### Exemplo 4 — mudar o threshold de confiança

```bash
CONFIDENCE_THRESHOLD=10 python -c "
from src.graph.build import build_graph
from src.graph.state import create_initial_state

graph = build_graph()
state = create_initial_state('Adicionar campo de observacoes no cadastro de fornecedores')
r = graph.invoke(state)
print('confidence:', r['confidence'], '| human_review_required:', r['human_review_required'])
"
```

Com o threshold baixo o suficiente, o mesmo requisito que escalaria com o padrão (70) publica direto (ou grava dry-run, se sem `issue_number`) — útil para testar o caminho de publicação automática sem depender de o Code Search já ter indexado evidência suficiente.

### Exemplo 5 — servidor MCP isolado

```bash
python -m src.mcp_server.server
```

Sobe via stdio; para inspecionar as tools registradas sem um client MCP completo, veja `tests/integration/test_mcp_server.py` (handshake via transporte em memória) como referência de como conectar.

## 3. O que ainda não é testável de ponta a ponta

- **Cenário 3 (entrada adversarial, seção 12 do PRD)** — `guard_adversarial` ainda é stub (sempre retorna `is_adversarial=False`); o bloqueio de instrução embutida chega no card 18. Até lá, qualquer texto passa.
- **RAG (`retrieve_rag`)** — sempre retorna lista vazia; chega no card 13. Até lá, a confiança nunca ganha os pontos de "padrão RAG recuperado".
- **Aprovação humana via `interrupt`** — hoje simulada escrevendo `approval_decision` direto no estado antes de invocar (exemplo 2); o fluxo real de suspender/retomar com checkpointer chega no card 15.

## 4. Onde olhar depois de rodar

- `audit/dry_run/{session_id}.md` — pareceres gravados em modo dry-run ou sem Issue de destino (pasta git-ignorada)
- Logs no console — `logging` com `extra={...}` estruturado; viram JSON de verdade no card 19 (`structlog`)
- `docs/evidencias/card-*.md` — cada card documenta a evidência real capturada quando foi implementado
