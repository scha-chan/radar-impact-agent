# Card 38 — Testes baseados em propriedade (Hypothesis)

**Branch/PR:** `feature/property-based-tests`
**Extensão pós-rubrica** (seção 21 do PRD) — cobrir invariantes de `src/domain/risk.py` sem viés de exemplo (seção 15 do PRD).

## O que foi implementado

`tests/property/test_risk_properties.py` (novo pacote `tests/property/`), com **Hypothesis**, cobrindo as três propriedades/relações metamórficas descritas na seção 15 do PRD — invariantes que exemplos isolados (os testes parametrizados de `tests/unit/test_risk.py`, com casos fixos) não capturam porque não exploram o espaço de entradas:

1. **`calculate_confidence` nunca sai de `[0, 100]`** — gerado com `ConfidenceInputs` arbitrário (`requirement_word_count`, `feature_type`, listas de `risks` de tamanho e conteúdo variados, etc.). Independente de quantas deduções se acumulem, o piso/teto (`max(0, min(100, score))`) precisa segurar.
2. **`aggregate_risk_level` nunca fica abaixo do maior risco individual da lista** — gerado com listas de `RiskItem` de tamanho e composição variados; compara o agregado contra `max()` dos níveis individuais.
3. **`classify_risk` é monotônico** — duas propriedades separadas (severidade fixa/probabilidade variando e vice-versa): aumentar severidade ou probabilidade nunca reduz o `risk_level` resultante. Usa `hypothesis.assume` para gerar só os pares ordenados (`a <= b`) relevantes à propriedade.

Estratégias reutilizáveis no topo do arquivo (`severities`, `probabilities`, `risk_items`, `confidence_inputs`) — `st.sampled_from` para os `IntEnum` (espaço pequeno e fechado, não faz sentido gerar valores fora dele) e `st.builds` para as dataclasses, compondo as estratégias de enum.

## Por que isso não é redundante com `tests/unit/test_risk.py`

Os testes parametrizados existentes (incluindo os 8 novos do card 37) travam **exemplos específicos e suas fronteiras exatas conhecidas** — good para documentar comportamento esperado caso a caso e para servir de sinal claro em `mutmut show`. As propriedades aqui travam uma **relação que precisa valer para qualquer entrada**, incluindo combinações que ninguém pensaria em escrever à mão (ex.: `requirement_word_count` negativo não faz sentido de domínio, mas 0 é válido e extremo; uma lista de 10 riscos todos sem mitigação testa o teto de dedução de um jeito que nenhum exemplo fixo cobre completamente). Se a fórmula de confiança for refatorada no futuro e algum caminho novo esquecer de clampar o resultado, um teste de exemplo só pega isso se por acaso gerar a combinação certa — a propriedade pega sempre, porque testa a invariante diretamente, não um valor esperado fixo.

## Verificação manual de que a monotonicidade realmente vale na matriz atual

Antes de escrever o teste, conferida manualmar a matriz `_RISK_MATRIX` (`src/domain/risk.py`) linha a linha nas duas direções (severidade crescente com probabilidade fixa, e vice-versa) — non-decreasing em ambas. As duas propriedades de monotonicidade passam sem ajuste na implementação; documentado aqui como confirmação consciente, não coincidência.

## `deadline=None`

Hypothesis por padrão falha um teste que ultrapassa 200ms por exemplo, para pegar regressões de performance — mas essas quatro propriedades chamam só funções puras (`classify_risk`/`aggregate_risk_level`/`calculate_confidence`, sem I/O), então uma variação de velocidade do runner de CI não deveria reprovar o teste por ser "lento", só a violação real da propriedade importa aqui.

## Testes

`pytest -q`: 267 passed (4 novos — cada teste de propriedade roda 100 exemplos gerados por padrão do Hypothesis, então na prática são centenas de casos exercitados), 4 skipped (Ollama real), 99,25% de cobertura. `ruff check .`/`ruff format --check .`: sem apontamentos.
