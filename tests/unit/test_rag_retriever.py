"""Testes do retriever sem dependência de Ollama nem de disco: a coleção é
um `EphemeralClient` do ChromaDB (em memória) com uma função de embedding
determinística e sem rede (hash do texto) — troca de lugar com
`build_embedding_function()` real via o parâmetro `collection` injetado.
"""

import itertools

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from src.rag import retriever as retriever_module
from src.rag.ingest import get_or_create_collection, ingest_corpus
from src.rag.retriever import retrieve_patterns

# `EphemeralClient()` compartilha armazenamento em processo por nome de
# coleção — um nome fixo faria os testes vazarem documentos uns para os
# outros quando rodam na mesma sessão do pytest. Cada teste pega um nome
# exclusivo desta sequência.
_collection_names = (f"test-patterns-{i}" for i in itertools.count())


class _HashEmbeddingFunction(EmbeddingFunction):
    """Embedding falso e determinístico: textos iguais (ou com os mesmos
    tokens) ficam próximos, sem chamar nenhum serviço externo. Implementa
    `__init__`/`name()` explicitamente (achado do card 26 — ver
    `_FakeEmbeddingFunction` em `test_rag_ingest.py`)."""

    def __init__(self) -> None:
        pass

    def __call__(self, input: Documents) -> Embeddings:  # noqa: A002
        return [_vector_for(text) for text in input]

    def name(self) -> str:
        return "hash-embedding-function"

    def get_config(self) -> dict:
        return {}


def _vector_for(text: str) -> list[float]:
    tokens = set(text.lower().split())
    vocabulary = [
        "login",
        "sessão",
        "senha",
        "upload",
        "arquivo",
        "listagem",
        "paginação",
        "recuperação",
    ]
    return [1.0 if word in tokens else 0.0 for word in vocabulary]


def _build_collection():
    client = chromadb.EphemeralClient()
    return get_or_create_collection(client, _HashEmbeddingFunction(), name=next(_collection_names))


def test_retrieve_patterns_returns_empty_for_outro_without_querying(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "src.rag.retriever._get_collection",
        lambda: calls.append("called"),
    )

    result = retrieve_patterns("outro", "qualquer texto")

    assert result == []
    assert calls == []


def test_retrieve_patterns_returns_empty_for_blank_query():
    collection = _build_collection()
    assert retrieve_patterns("login", "   ", collection=collection) == []


def test_retrieve_patterns_filters_by_feature_type():
    collection = _build_collection()
    collection.upsert(
        ids=["login#1", "upload#1"],
        documents=["login sessão senha", "upload arquivo"],
        metadatas=[
            {
                "feature_type": "login",
                "area": "authentication",
                "pattern_name": "p1",
                "source": "login#1",
            },
            {
                "feature_type": "upload",
                "area": "storage",
                "pattern_name": "p2",
                "source": "upload#1",
            },
        ],
    )

    patterns = retrieve_patterns(
        "login", "login sessão senha", collection=collection, similarity_threshold=0.0
    )

    assert len(patterns) == 1
    assert patterns[0].source == "login#1"


def test_retrieve_patterns_discards_results_below_similarity_threshold():
    collection = _build_collection()
    collection.upsert(
        ids=["login#1"],
        documents=["upload arquivo"],  # nao compartilha nenhum token com a query
        metadatas=[
            {"feature_type": "login", "area": "x", "pattern_name": "p1", "source": "login#1"}
        ],
    )

    patterns = retrieve_patterns(
        "login", "login sessão senha", collection=collection, similarity_threshold=0.99
    )

    assert patterns == []


def test_retrieve_patterns_respects_top_k():
    collection = _build_collection()
    collection.upsert(
        ids=[f"login#{i}" for i in range(5)],
        documents=["login sessão"] * 5,
        metadatas=[
            {"feature_type": "login", "area": "x", "pattern_name": f"p{i}", "source": f"login#{i}"}
            for i in range(5)
        ],
    )

    patterns = retrieve_patterns(
        "login", "login sessão", collection=collection, top_k=2, similarity_threshold=0.0
    )

    assert len(patterns) == 2


def test_retrieve_patterns_over_ingested_real_corpus_returns_matching_feature_type():
    collection = _build_collection()
    ingest_corpus(collection)

    patterns = retrieve_patterns(
        "login", "login senha sessão", collection=collection, similarity_threshold=0.0
    )

    assert patterns
    assert all(pattern.source.startswith("knowledge/login.md#") for pattern in patterns)


def test_retrieve_patterns_falls_back_to_empty_when_query_fails():
    class _BrokenCollection:
        def query(self, **_kwargs):
            raise RuntimeError("chroma indisponível")

    result = retrieve_patterns("login", "algo", collection=_BrokenCollection())

    assert result == []


def test_retrieve_patterns_lazily_builds_and_caches_the_default_collection(monkeypatch):
    # Sem `collection` explicito, retrieve_patterns usa _get_collection() -
    # o caminho lazy que a producao usa de verdade (ChromaDB persistente +
    # Ollama, card 13). Mocado aqui para nao depender de rede/disco.
    collection = _build_collection()
    collection.upsert(
        ids=["login#1"],
        documents=["login senha sessão"],
        metadatas=[
            {"feature_type": "login", "area": "x", "pattern_name": "p1", "source": "login#1"}
        ],
    )
    calls = {"get_client": 0, "get_or_create_collection": 0, "ingest_corpus": 0}

    monkeypatch.setattr(retriever_module, "_collection", None)
    monkeypatch.setattr(
        retriever_module,
        "get_client",
        lambda: calls.update(get_client=calls["get_client"] + 1) or object(),
    )
    monkeypatch.setattr(
        retriever_module,
        "get_or_create_collection",
        lambda client, ef: (
            calls.update(get_or_create_collection=calls["get_or_create_collection"] + 1)
            or collection
        ),
    )
    monkeypatch.setattr(retriever_module, "build_embedding_function", _HashEmbeddingFunction)
    monkeypatch.setattr(
        retriever_module,
        "ingest_corpus",
        lambda coll: calls.update(ingest_corpus=calls["ingest_corpus"] + 1),
    )

    patterns = retrieve_patterns("login", "login senha sessão", similarity_threshold=0.0)

    assert patterns
    assert calls == {"get_client": 1, "get_or_create_collection": 1, "ingest_corpus": 0}

    # segunda chamada reusa o singleton cacheado no modulo - nao reconstroi o client.
    retrieve_patterns("login", "login senha sessão", similarity_threshold=0.0)
    assert calls["get_client"] == 1


def test_retrieve_patterns_ingests_corpus_when_default_collection_is_empty(monkeypatch):
    empty_collection = _build_collection()

    monkeypatch.setattr(retriever_module, "_collection", None)
    monkeypatch.setattr(retriever_module, "get_client", lambda: object())
    monkeypatch.setattr(
        retriever_module, "get_or_create_collection", lambda client, ef: empty_collection
    )
    monkeypatch.setattr(retriever_module, "build_embedding_function", _HashEmbeddingFunction)
    ingested = []
    monkeypatch.setattr(retriever_module, "ingest_corpus", lambda coll: ingested.append(coll))

    retrieve_patterns("login", "login senha sessão", similarity_threshold=0.0)

    assert ingested == [empty_collection]
