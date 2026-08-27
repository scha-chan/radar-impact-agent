# Card 37 — Mutation testing nos módulos críticos

**Branch/PR:** `feature/mutation-testing`
**Extensão pós-rubrica** (seção 21 do PRD) — RNF-10: mutation score acima de 60% em `src/domain/` e `src/governance/`, medido com `mutmut`.

## mutmut 3.x foi descartado — incompatibilidade real, não só "não roda no Windows"

A tentativa inicial usou `mutmut==3.7.0` (a versão mais recente), configurado via `[tool.mutmut]` em `pyproject.toml`. `mutmut run` **não roda nativamente no Windows** (mensagem própria da ferramenta: "please use the WSL") — mesma classe de limitação já documentada para Docker (cards 25/26/29/30). WSL também não está instalado nesta máquina, então a primeira validação real só foi possível rodando o job no CI (`ubuntu-latest`).

No CI, a versão 3.x revelou um problema mais sério que "só funciona no Linux": sua instrumentação interna ("trampoline", usada para rastrear cobertura por mutante) **assume convenção de packaging src-layout**, em que `src/` é só um diretório físico removido do caminho de import por ferramentas de build — nessa convenção, o código nunca importa como `from src.xxx import ...`, e sim `from xxx import ...` direto. Uma asserção interna do mutmut (`assert not name.startswith("src.")`, `mutmut/__main__.py:123`) trava exatamente essa suposição. Este projeto, porém, importa de verdade como `from src.domain.risk import ...` — `src/` tem `__init__.py`, é um pacote Python real, não removido do caminho de import — uma escolha deliberada mantida desde o card 1. O resultado, reproduzido três vezes no CI com diagnóstico (`debug=true`) até isolar a causa:

```
AssertionError: Failed trampoline hit. Module name starts with `src.`, which is invalid
```

Nenhuma combinação de `source_paths`/`only_mutate`/`also_copy` contorna essa asserção — ela dispara para qualquer chamada a uma função de um módulo mutado, independente de qual diretório é declarado como raiz. Trocar a estrutura de imports do projeto inteiro (~30 arquivos) só para acomodar uma ferramenta de mutation testing não seria uma troca razoável.

## Solução: `mutmut==2.5.1`

A série 2.x usa reescrita de AST simples (sem a instrumentação "trampoline" da 3.x) e **não tem essa suposição** — funciona com o layout real deste projeto. Como bônus, roda nativamente no Windows, o que permitiu validar a configuração inteira localmente antes de depender só do CI.

Configuração (`pyproject.toml`, `[tool.mutmut]`):
```toml
paths_to_mutate = "src/domain/,src/governance/"
runner = "python -m pytest -x -q --no-cov tests/unit/test_risk.py tests/unit/test_adversarial.py tests/unit/test_permissions.py tests/unit/test_tool_executor.py"
```
`--no-cov` neutraliza `--cov-fail-under=70` (herdado de `[tool.pytest.ini_options].addopts`, que se aplica a toda chamada de pytest, inclusive as do mutmut) — os quatro arquivos de teste selecionados cobrem só `src/domain/`+`src/governance/`, muito abaixo de 70% do `src/` inteiro.

`src/quality/mutation_gate.py` (novo): lê o relatório `mutmut junitxml` (cada `<testcase>` é um mutante; `<failure>`=sobreviveu, `<error>`=timeout) e calcula `score = (total - sobreviventes - timeouts) / total`; falha (exit 1) se abaixo do mínimo (60%, RNF-10). Job `mutation-testing` no CI: `mutmut run --CI` → `mutmut junitxml > mutmut-report.xml` → `python -m src.quality.mutation_gate mutmut-report.xml --min-score 60`.

## Rodado de verdade, localmente (Windows, mutmut 2.5.1)

Primeira execução real, sem nenhum ajuste de teste: **148 mutantes, 82 mortos, 66 sobreviventes — score 55,4%**, abaixo do mínimo de 60% (RNF-10). Isso é exatamente o gap que mutation testing existe para expor — os módulos já tinham cobertura de linha alta (card 36), mas quase metade das mutações passava despercebida. `mutmut results`/`mutmut show <id>` revelaram os padrões reais de teste fraco:

- **Valores de `IntEnum` nunca verificados diretamente** (`Severity`, `Probability`, `RiskLevel`) — todos os testes existentes comparam por nome (`Severity.LOW`), nunca pelo inteiro subjacente. Mutar `LOW = 1` para `LOW = None` sobrevivia porque nada comparava contra o valor bruto.
- **Limites exatos não testados** — `distinct_evidence_sources < MIN_DISTINCT_EVIDENCE_SOURCES` mutado para `<=` sobrevivia porque nenhum teste cobria o caso `distinct_evidence_sources == MIN_DISTINCT_EVIDENCE_SOURCES` exatamente (só valores claramente acima/abaixo). Mesmo padrão para `SHORT_REQUIREMENT_WORD_THRESHOLD`.
- **Constantes de dedução mutadas sem detecção** (`MIN_DISTINCT_EVIDENCE_SOURCES=2→3`, `SHORT_REQUIREMENT_WORD_THRESHOLD=15→16`) — os testes de limiar existentes usavam valores longe da fronteira, então um deslocamento de 1 na constante não mudava o resultado do teste.
- **`@dataclass(frozen=True)` de `RiskItem` nunca testado** — mutado para `frozen=False` sobrevivia porque nenhum teste tentava mutar uma instância e esperar `FrozenInstanceError`.
- **Default de campo de dataclass nunca exercitado** (`ConfidenceInputs.tools_failed_with_fallback: int = 0`) — todo teste passava esse campo explicitamente; o valor default do próprio código nunca era testado.

`tests/unit/test_risk.py` ganhou 8 testes novos atacando exatamente esses pontos (valores de enum, limites exatos nas duas pontas, defaults de dataclass, imutabilidade). Reexecutando: **148 mutantes, 98 mortos, 50 sobreviventes — score 66,2%**, acima do mínimo.

Os 50 sobreviventes restantes (não perseguidos neste card — ponto de parada consciente, mesmo padrão de decisões anteriores como o card 26) incluem mutantes prováveis de serem **equivalentes** — ex.: mutar `mitigation: str | None = None` para `str & None = None` nunca executa em runtime porque `from __future__ import annotations` guarda anotações como string, nunca avaliadas — não há como um teste de comportamento detectar isso sem inspecionar a AST/string da anotação, o que estaria fora do escopo de um teste de unidade normal.

## Testes

`tests/unit/test_mutation_gate.py`: `compute_mutation_score`/`parse_junitxml`/`check_mutation_score`/`main` com relatórios JUnit XML sintéticos (sobreviventes, timeouts, score exato no limite). `tests/unit/test_risk.py`: os 8 testes novos descritos acima.

`pytest -q`: 263 passed (16 novos: 8 em `test_risk.py`, mais a reescrita de `test_mutation_gate.py`), 4 skipped, 99,25% de cobertura (100% em `src/quality/mutation_gate.py`). `ruff check .`/`ruff format --check .`: sem apontamentos. Mutation score real medido localmente: **66,2%** (acima do mínimo de 60%, RNF-10) — o job `mutation-testing` do CI reproduz o mesmo cálculo a cada execução.
