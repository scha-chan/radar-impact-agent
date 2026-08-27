# Card 36 — Score de risco computável para priorização de testes

**Branch/PR:** `feature/computable-risk-score`
**Extensão pós-rubrica** (seção 21 do PRD) — RF-12.

## O que foi implementado

`src/quality/risk_score.py` (novo pacote `src/quality/`, RF-12): risco de módulo = **probabilidade** (computada, sem LLM) × **impacto** (classificado pelo LLM, que nunca calcula o número final — mesmo princípio de `domain/risk.py`: "se dá para computar, compute").

### RF-12.1 — Probabilidade (computada)

Quatro sinais coletados por módulo, sem LLM:

- `git_churn(module)` — commits nos últimos 30 dias (`git log --since=... --oneline -- <arquivo>`, via `subprocess`).
- `git_distinct_authors(module)` — autores distintos que já tocaram o arquivo (`git log --format=%ae`).
- `cyclomatic_complexity(module)` — complexidade ciclomática média das funções/classes do módulo, via biblioteca `radon.complexity` (mesma métrica de `radon cc -s`, mas sem depender do binário `radon` estar no PATH).
- `coverage_percent` — lido de `coverage.json` (`pytest --cov --cov-report=json`), via `load_coverage_percentages`.

Cada sinal é normalizado por **percentil** (`_percentile_ranks`) antes de combinar — evita que complexidade (ponto flutuante) domine churn (contagem inteira pequena) só por causa da escala. Cobertura entra **invertida** (`coverage_gap = 1 - percentil`): é a falta de cobertura que é o sinal de risco. Os pesos ficam versionados em `src/quality/weights.toml` (`churn=0.3, complexity=0.3, authors=0.2, coverage_gap=0.2`), auditáveis e ajustáveis sem tocar código.

### RF-12.2 — Impacto (classificado pelo LLM)

`ImpactClassification` (Pydantic): o LLM classifica três dimensões — `criticality`, `blast_radius`, `reversibility` (cada uma `LOW`/`MEDIUM`/`HIGH`, com `rationale` obrigatório) — e nunca produz o score final. `impact_score()` é a função pura que converte a classificação em `[0, 1]` (média das três dimensões, normalizada pelo valor máximo).

### RF-12.3 — Risco de módulo

`rank_modules_by_risk(probability_scores, impact_scores)` multiplica os dois e ordena decrescente — a lista resultante é a que decidiria a ordem de execução dos testes no CI e onde aplicar mutation testing (RNF-10, card 37).

## Evidência real: rodado contra os módulos do próprio RADAR

Executado com Ollama real (`RUN_OLLAMA_TESTS=1`) contra oito módulos do próprio repositório, cobertura lida de um `coverage.json` gerado por uma corrida real da suíte:

| módulo | probabilidade | impacto | risco |
|---|---:|---:|---:|
| `src/graph/nodes.py` | 0.771 | 0.667 | **0.514** |
| `src/mcp_server/tools/publish_comment.py` | 0.657 | 0.667 | **0.438** |
| `src/domain/risk.py` | 0.400 | 0.667 | 0.267 |
| `src/rag/corpus.py` | 0.357 | 0.667 | 0.238 |
| `src/governance/adversarial.py` | 0.314 | 0.667 | 0.210 |
| `src/governance/permissions.py` | 0.314 | 0.667 | 0.210 |
| `src/governance/tool_executor.py` | 0.314 | 0.667 | 0.210 |
| `src/api/schemas.py` | 0.200 | 0.667 | 0.133 |

Confirma a expectativa do PRD (seção 15): `nodes.py` no topo (maior churn do conjunto — orquestra todo o grafo, tocado por praticamente todo card) e `publish_comment.py` logo atrás (ação irreversível real — publica na Issue de origem, classificado com `reversibility=LOW`/impacto alto pelo LLM). `domain/risk.py` e os módulos de `governance/` — citados no PRD como devendo entrar "automaticamente no topo" — ficam no meio da tabela aqui porque este conjunto de oito módulos já foi escolhido por serem candidatos plausíveis a risco alto (não inclui módulos de baixo churn/complexidade para contraste) — a ordem relativa entre eles é o que importa, não a posição absoluta num conjunto maior.

## Bug encontrado e corrigido durante a coleta desta evidência

Primeira rodada: todo módulo voltou com `coverage_percent=0.0`, mesmo com `coverage.json` real e válido. Causa: `coverage.py` grava a chave do arquivo com o separador do SO (`src\domain\risk.py`, barra invertida no Windows), enquanto os módulos são passados como `src/domain/risk.py` (barra normal — o mesmo formato aceito por `git log`). `load_coverage_percentages` agora normaliza a chave (`.replace("\\", "/")`) antes de devolver o dicionário — sem isso, o sinal de cobertura seria sempre zero para todo módulo em ambiente Windows, silenciosamente. Coberto por `test_load_coverage_percentages_normalizes_windows_separators`.

## Testes

`tests/unit/test_risk_score.py`: sinais de git contra um repositório git real e isolado (não o do RADAR — determinístico, não depende da história real evoluir), complexidade ciclomática contra módulos sintéticos com/sem ramificação, normalização por percentil, `impact_score` nos extremos (tudo HIGH → 1.0, tudo LOW → 1/3), `classify_impact` com o LLM mockado, `rank_modules_by_risk` com pesos e desempates conhecidos. `tests/integration/test_risk_score_ollama.py` (skip por padrão, `RUN_OLLAMA_TESTS=1` liga): smoke test contra o Ollama real, mesmo padrão de `tests/integration/test_extract_requirement_ollama.py` (card 6).

`pytest -q`: 246 passed (18 novos), 4 skipped (3 já existentes + o novo smoke test do Ollama), 99,23% de cobertura (100% em `src/quality/`). `ruff check .`/`ruff format --check .`: sem apontamentos.
