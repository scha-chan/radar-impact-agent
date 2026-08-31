import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from src.rag.ingest import get_client, get_or_create_collection, ingest_corpus


class _FakeEmbeddingFunction(EmbeddingFunction):
    """Vetor fixo — só interessa aqui quantos chunks entram na coleção, não
    a qualidade da recuperação (isso é `test_rag_retriever.py`). Implementa
    `__init__`/`name()` explicitamente — achado do card 26 (análise do log
    do job "test" da CI): sem isso, o chromadb emite `DeprecationWarning`
    a cada uso, hoje silenciosa mas anunciada para virar erro."""

    def __init__(self) -> None:
        pass

    def __call__(self, input: Documents) -> Embeddings:  # noqa: A002
        return [[1.0, 0.0] for _ in input]

    def name(self) -> str:
        return "fake-embedding-function"

    def get_config(self) -> dict:
        return {}


def _build_collection(name: str):
    client = chromadb.EphemeralClient()
    return get_or_create_collection(client, _FakeEmbeddingFunction(), name=name)


def test_ingest_corpus_loads_at_least_50_chunks_from_real_knowledge_dir():
    collection = _build_collection("ingest-real")

    count = ingest_corpus(collection)

    assert count >= 50
    assert collection.count() == count


def test_ingest_corpus_is_idempotent(tmp_path):
    knowledge_dir = tmp_path
    (knowledge_dir / "login.md").write_text(
        "## Padrão A\n\n**Área:** authentication\n**Descrição:** d\n"
        "**Riscos típicos:** r\n**Dependências comuns:** dep\n"
        "**Testes recomendados:** t\n",
        encoding="utf-8",
    )
    collection = _build_collection("ingest-idempotent")

    first_count = ingest_corpus(collection, knowledge_dir=knowledge_dir)
    second_count = ingest_corpus(collection, knowledge_dir=knowledge_dir)

    assert first_count == 1
    assert second_count == 1
    assert collection.count() == 1


def test_ingest_corpus_returns_zero_for_empty_directory(tmp_path):
    collection = _build_collection("ingest-empty")

    count = ingest_corpus(collection, knowledge_dir=tmp_path)

    assert count == 0
    assert collection.count() == 0


def test_get_client_returns_a_usable_persistent_client(tmp_path):
    client = get_client(str(tmp_path / "chroma-data"))
    collection = get_or_create_collection(client, _FakeEmbeddingFunction(), name="smoke")

    collection.upsert(ids=["a"], documents=["x"], metadatas=[{"feature_type": "login"}])

    assert collection.count() == 1
