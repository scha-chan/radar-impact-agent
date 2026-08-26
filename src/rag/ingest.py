"""Ingestão do corpus de padrões de impacto no índice vetorial (RF-03.2,
card 13). Constrói/atualiza a coleção ChromaDB persistente a partir de
`knowledge/*.md` (card 12) — o retriever (`retriever.py`) só consulta o que
foi ingerido aqui.

Executável como script (`python -m src.rag.ingest`) para popular o índice
antes de subir a aplicação; `retriever.py` também chama `ingest_corpus` sob
demanda se a coleção estiver vazia, para o RAG funcionar out-of-the-box em
desenvolvimento/testes.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import chromadb
from chromadb.api.types import EmbeddingFunction

from src import config  # noqa: F401 - carrega .env como efeito colateral do import
from src.rag.corpus import load_corpus

logger = logging.getLogger(__name__)

# "chroma" (sem barra) para casar com o padrão "chroma/" do .gitignore
# (seção 13 do PRD: dados de índice não são versionados).
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "chroma")
COLLECTION_NAME = "impact_patterns"
KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge"


def get_client(persist_dir: str | None = None) -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=persist_dir or CHROMA_PERSIST_DIR)


def get_or_create_collection(
    client: chromadb.ClientAPI,
    embedding_function: EmbeddingFunction,
    name: str = COLLECTION_NAME,
):
    return client.get_or_create_collection(
        name=name,
        embedding_function=embedding_function,
        # cosine: a similaridade recuperada precisa ser comparável ao limiar
        # da fórmula de confiança (seção 11 do PRD), independente da norma
        # dos vetores do modelo de embedding escolhido.
        metadata={"hnsw:space": "cosine"},
    )


def ingest_corpus(collection, knowledge_dir: Path = KNOWLEDGE_DIR) -> int:
    """Faz upsert de cada padrão de `knowledge_dir` como um chunk.

    Idempotente: o id de cada chunk é o próprio `source`
    (`knowledge/<tipo>.md#<slug>`), então reexecutar a ingestão atualiza os
    chunks existentes em vez de duplicá-los.
    """
    documents = load_corpus(knowledge_dir)
    if not documents:
        return 0

    collection.upsert(
        ids=[doc.source for doc in documents],
        documents=[doc.content for doc in documents],
        metadatas=[
            {
                "feature_type": doc.feature_type,
                "area": doc.area,
                "pattern_name": doc.pattern_name,
                "source": doc.source,
            }
            for doc in documents
        ],
    )
    return len(documents)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    from src.rag.embeddings import build_embedding_function

    client = get_client()
    collection = get_or_create_collection(client, build_embedding_function())
    count = ingest_corpus(collection)
    logger.info("rag_ingest_completed", extra={"chunks": count, "collection_total": collection.count()})


if __name__ == "__main__":
    main()
