# Análise de logs do pipeline com IA

**Card:** 26 — Análise de logs do pipeline com IA
**Fonte dos logs:** execuções reais do workflow `CI` (`.github/workflows/ci.yml`, card 25) no GitHub Actions — [run #33013041270](https://github.com/scha-chan/radar-impact-agent/actions/runs/33013041270) (falhou) e [run #33013358793](https://github.com/scha-chan/radar-impact-agent/actions/runs/33013358793) (passou), obtidos via `gh run view --log --job <id>`.

Duas etapas analisadas: **`test`** e **`build`**, conforme a sugestão da seção 16 do PRD.

---

## Etapa 1 — `test` (`pytest --cov --cov-report=term-missing`)

### Log bruto (recorte relevante)

```
=============================== warnings summary ===============================
tests/integration/test_human_approval.py::test_expired_approval_archives_even_when_late_decision_is_approved
  /opt/hostedtoolcache/Python/3.13.15/x64/lib/python3.13/site-packages/langgraph/checkpoint/sqlite/__init__.py:468: ResourceWarning: unclosed database in <sqlite3.Connection object at 0x7fb34e41be20>
    cur.executemany(

tests/unit/test_rag_ingest.py: 4 warnings
tests/unit/test_rag_retriever.py: 7 warnings
  /opt/hostedtoolcache/Python/3.13.15/x64/lib/python3.13/site-packages/chromadb/api/types.py:944: DeprecationWarning: The EmbeddingFunction class does not implement name(). This will be required in a future version.
    self.name() is NotImplemented

[... mais warnings do mesmo tipo ...]

================= 167 passed, 3 skipped, 46 warnings in 7.24s ==================
```

### Explicação produzida

167 testes passaram e a suíte bateu o gate de cobertura (99,10%, card 22) — nenhum problema bloqueante. Mas **46 warnings** é um número alto o suficiente para esconder um sinal real dentro do ruído, então valia a pena separar por categoria em vez de ignorar:

1. **`ResourceWarning: unclosed database`** — conexões `sqlite3` abertas por testes de integração do checkpointer (cards 15/16/22/23) nunca eram fechadas. Cada teste que constrói um `SqliteSaver` diretamente (`sqlite3.connect(...)`) segurava a conexão até o processo Python terminar; o coletor de lixo eventualmente fechava, gerando o aviso, mas de forma não determinística — o mesmo motivo pelo qual esse tipo de warning é perigoso: um vazamento real de recurso em produção teria o mesmo sintoma, só que sem o coletor de lixo por perto para "salvar" o processo.
2. **`DeprecationWarning: ... does not implement name()`** — os dublês de teste (`_FakeEmbeddingFunction`, `_HashEmbeddingFunction`, cards 13/22) implementam só `__call__` do protocolo `EmbeddingFunction` do ChromaDB; a biblioteca anuncia que `__init__`/`name()`/`get_config()` vão virar obrigatórios numa versão futura.

### O que foi corrigido a partir dela

- **`tests/helpers.py`** ganhou `sqlite_checkpointer()`/`close_all_sqlite_connections()` — toda conexão sqlite de teste passa a ser registrada e fechada automaticamente por um fixture `autouse` em `tests/conftest.py`, ao final de cada teste. `tests/integration/test_human_approval.py` e `test_scenario_2_high_risk_escalation.py` (que tinham a mesma função `_checkpointer` duplicada) foram migrados para o helper compartilhado; `test_checkpointer.py` (card 22) fecha a conexão explicitamente via `checkpointer.conn.close()`.
- `_FakeEmbeddingFunction`/`_HashEmbeddingFunction` ganharam `__init__`/`name()`/`get_config()`.
- `tests/unit/test_publish_comment.py` — um `open(...).read()` sem context manager também aparecia como `ResourceWarning: unclosed file`; trocado por `with open(...) as f`.

**Resultado:** 46 → **12 warnings**. Os 12 restantes são de dois tipos que ficaram deliberadamente sem correção, documentados abaixo em vez de silenciados às pressas.

### O que foi analisado e conscientemente não corrigido

- **1 warning**: `chromadb/telemetry/opentelemetry/__init__.py` usa `asyncio.iscoroutinefunction` (depreciado desde Python 3.12) — é código interno da biblioteca `chromadb`, não do projeto; não há nada para corrigir do nosso lado além de esperar uma versão nova do pacote.
- **11 warnings**: tentei fechar completamente a cadeia de depreciação do `EmbeddingFunction` adicionando também `build_from_config()` aos dois dublês — isso **piorou** a situação: o registro interno do ChromaDB passou a chamar `_FakeEmbeddingFunction.name()` sem instância (`TypeError: missing 1 required positional argument: 'self'`), um comportamento que parece ser uma interação específica da versão `1.5.9` do `chromadb` com uma classe que implementa `build_from_config` como `staticmethod`, não um bug do nosso teste. Revertido — ponto de parada deliberado: perseguir a régua de depreciação mais nova de uma biblioteca de terceiros até o fim tem retorno decrescente quando a própria tentativa introduz um problema pior que o original.

---

## Etapa 2 — `build` (`docker build -t radar:ci .`)

### Log bruto (recorte relevante)

```
#9 [4/6] RUN pip install --no-cache-dir -r requirements.txt
#9 18.95 Successfully installed aiohappyeyeballs-2.7.1 ... langgraph-1.2.11
#9 18.95 WARNING: Running pip as the 'root' user can result in broken permissions
   and conflicting behaviour with the system package manager, possibly rendering
   your system unusable. It is recommended to use a virtual environment instead:
   https://pip.pypa.io/warnings/venv. Use the --root-user-action option if you
   know what you are doing and want to suppress this warning.
...
#12 writing image sha256:2b0d38ff... done
#12 naming to docker.io/library/radar:ci done
#12 DONE 2.1s
```

### Explicação produzida

O build passou (imagem `radar:ci` construída com sucesso em ~36s, a maior parte — 21,4s — só instalando dependências). O único ponto de atenção real é o aviso do `pip`: como o `Dockerfile` não define nenhum `USER`, toda a imagem — incluindo o processo da aplicação em tempo de execução (`CMD`), não só a etapa de instalação — rodava como `root` dentro do container. Isso não afeta o resultado do `docker build` em si (o aviso é sobre a instalação, que legitimamente precisa ser root para escrever em `/usr/lib/python.../site-packages`), mas é uma prática de segurança de containers a evitar: um processo comprometido rodando como root dentro do container tem mais superfície de ataque do que um processo sem privilégios, mesmo estando isolado do host.

### O que foi corrigido a partir dela

`Dockerfile`: adicionado `RUN useradd --create-home --shell /bin/bash radar` e `USER radar` **depois** da instalação de dependências — a instalação continua rodando como root (é necessário para escrever no `site-packages` do sistema), mas o `CMD` final (o processo de verdade, de vida longa) roda sem privilégios.

**Limitação conhecida, não corrigida agora:** com `USER radar` ativo, o processo perde permissão de escrita em `/app` (criado pelas camadas anteriores como `root`) — hoje isso não quebra nada porque o `CMD` atual só sobe o servidor MCP (stdio, card 07), que não escreve arquivo nenhum na inicialização. Quando a API (card 30) existir e o container precisar escrever `chroma/`, `audit/` ou o checkpoint sqlite dentro do volume montado (`docker-compose.yml`, RNF-06), será preciso ajustar a propriedade do diretório do volume (`chown radar:radar` no entrypoint, ou um volume com permissões abertas) — registrado aqui para não ser esquecido, não implementado agora porque não há nada rodando ainda que exercite esse caminho.

---

## Resultado

- **Etapa `test`**: 46 → 12 warnings (-74%), com dois vetores de vazamento de recurso real corrigidos (conexões sqlite e um arquivo aberto sem context manager) e uma tentativa de correção adicional revertida conscientemente por piorar o comportamento.
- **Etapa `build`**: imagem passa a rodar sem privilégios de root em produção; limitação de permissão de volume documentada para quando a API (card 30) tornar esse caminho real.
- `pytest -q`: 167 passed, 3 skipped (Ollama real), 99,10% de cobertura, sem regressão. `ruff check .`/`ruff format --check .`: sem apontamentos.
