# Card 13 — Implementar ingestão e retriever

**Branch/PR:** `feature/rag-padroes`
**Resultado esperado (Kanban):** Recuperação semântica → Padrões recuperados por tipo de feature

## O que foi implementado

- `src/rag/corpus.py` — parsing puro de `knowledge/*.md` (card 12) em `PatternDocument` (um por seção `##`), sem dependência de ChromaDB. `README.md` é ignorado por não ser conteúdo do corpus.
- `src/rag/embeddings.py` — `build_embedding_function()`, mesmo princípio de `graph/llm.py`: Ollama local por padrão (`OLLAMA_EMBED_MODEL`, default `nomic-embed-text`), isolado atrás de uma fábrica para trocar de provedor sem tocar em `ingest.py`/`retriever.py`.
- `src/rag/ingest.py` — `ingest_corpus()` faz upsert idempotente (id = `source`, ex.: `knowledge/login.md#autenticação-e-sessão`) na coleção ChromaDB persistente (`CHROMA_PERSIST_DIR`, default `chroma/` — já coberto pelo `.gitignore`). Executável como script (`python -m src.rag.ingest`).
- `src/rag/retriever.py` — `retrieve_patterns(feature_type, query_text)`: filtra por `feature_type` via metadado (`where`) e descarta resultados abaixo de `RAG_SIMILARITY_THRESHOLD` (seção 11 do PRD — "nenhum padrão RAG recuperado acima do limiar" penaliza a confiança). Lazy-init: se a coleção estiver vazia na primeira chamada, ingere o corpus automaticamente.
- `src/graph/nodes.py::retrieve_rag` deixou de ser stub — chama `retrieve_patterns` de verdade e popula `evidence_sources` (RF-03.4) com `type="rag"` e `ref=pattern.source`.
- `.env.example` ganhou `OLLAMA_EMBED_MODEL`, `CHROMA_PERSIST_DIR`, `RAG_TOP_K`, `RAG_SIMILARITY_THRESHOLD`. `requirements.txt` ganhou `chromadb==1.5.9`.

## Decisão: `feature_type == "outro"` nunca consulta o índice

`outro` não tem arquivo dedicado em `knowledge/` (decisão documentada no card 12) — consultar por ele sempre voltaria vazio pelo filtro de metadado. `retrieve_patterns` retorna `[]` antes de tocar a coleção nesse caso, evitando uma chamada de embedding ao Ollama que nunca encontraria nada. Efeito colateral bom para os testes: os testes de topologia do grafo (`test_graph.py`, `test_evidence_parallelism.py`) usam `feature_type="outro"` e continuam rodando sem exigir Ollama nem ChromaDB reais.

## Por que "cosine" como espaço da coleção

`hnsw:space="cosine"` faz a distância do ChromaDB variar em `[0, 2]` (`distance = 1 - similaridade_cosseno`), então `similarity = 1 - distance` fica em `[-1, 1]` e comparável ao limiar da fórmula de confiança independente da norma dos vetores do modelo de embedding escolhido — trocar `OLLAMA_EMBED_MODEL` no futuro não exige recalibrar `RAG_SIMILARITY_THRESHOLD`.

## Testes

- `tests/unit/test_rag_corpus.py` — parsing isolado (arquivo sintético) e uma checagem de integração leve contra o corpus real (`knowledge/`): ≥ 50 chunks, sem `outro`, toda `Área` preenchida.
- `tests/unit/test_rag_ingest.py` — `ingest_corpus` sobre o corpus real (≥ 50 chunks), idempotência (upsert não duplica), diretório vazio retorna zero.
- `tests/unit/test_rag_retriever.py` — filtro por `feature_type`, descarte abaixo do limiar de similaridade, respeito a `top_k`, fallback para lista vazia quando a consulta falha (RF-03.5), `outro` nunca toca a coleção. Usa `chromadb.EphemeralClient()` com uma função de embedding falsa e determinística (hash de tokens) injetada via o parâmetro `collection` — nenhum teste depende de Ollama rodando.
- Achado durante os testes: `EphemeralClient()` compartilha armazenamento em processo por *nome* de coleção — testes que reusassem o mesmo nome vazavam documentos uns para os outros quando rodavam na mesma sessão do pytest. Corrigido dando um nome exclusivo por teste (contador `itertools.count()`).

## Decisões técnicas

- Retriever aceita `collection` injetado (parâmetro opcional) — é o que permite testar contra um índice em memória sem depender de Ollama/disco, seguindo o mesmo padrão de injeção de dependência já usado em `search_code`/`fetch_history` (parâmetro `failures`).
- `retrieve_rag` usa `" ".join(search_terms) or requirement.text` como consulta — diferente de `search_codebase`/`fetch_history`, que precisam de termos exatos para a API de busca do GitHub, a recuperação semântica ainda funciona bem com o texto bruto do requisito quando a extração não gerou termos.
- Nenhuma exceção do ChromaDB derruba o grafo (RF-03.5): falha na consulta é logada e tratada como "nenhum padrão encontrado", igual ao fallback já existente em `search_code`/`fetch_history`.
