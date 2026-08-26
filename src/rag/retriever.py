"""Tool `retrieve_patterns` — RF-03.2: recupera do RAG os padrões de impacto
do tipo de feature identificado (card 13 — recuperação semântica).

Usa a coleção ChromaDB ingerida por `ingest.py`. Filtra por dois critérios:

- `feature_type`, via metadado (`where`) — um padrão de "login" nunca deve
  aparecer para um requisito de "upload", mesmo que o texto seja
  semanticamente próximo;
- limiar de similaridade (seção 11 do PRD) — abaixo dele, o padrão é
  descartado. Retornar nada quando a evidência é fraca é o comportamento
  correto: `rag_patterns_found=False` penaliza a confiança em `score_risk`
  em vez de o parecer citar um padrão pouco relacionado como se fosse
  evidência sólida.
"""

from __future__ import annotations

import logging
import os

from src import config  # noqa: F401 - carrega .env como efeito colateral do import
from src.graph.state import PatternChunk
from src.rag.embeddings import build_embedding_function
from src.rag.ingest import get_client, get_or_create_collection, ingest_corpus

logger = logging.getLogger(__name__)

RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))
RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.3"))

# "outro" é o catch-all sem arquivo dedicado em knowledge/ (decisão do card
# 12) — consultar o índice para ele nunca encontra nada por `feature_type`,
# então nem vale acionar o embedding da query (evita uma chamada ao Ollama
# que sempre daria em vazio).
_NO_CORPUS_FEATURE_TYPE = "outro"

_collection = None


def _get_collection():
    global _collection
    if _collection is None:
        client = get_client()
        _collection = get_or_create_collection(client, build_embedding_function())
        if _collection.count() == 0:
            ingest_corpus(_collection)
    return _collection


def retrieve_patterns(
    feature_type: str,
    query_text: str,
    *,
    collection=None,
    top_k: int = RAG_TOP_K,
    similarity_threshold: float = RAG_SIMILARITY_THRESHOLD,
) -> list[PatternChunk]:
    if feature_type == _NO_CORPUS_FEATURE_TYPE or not query_text.strip():
        return []

    try:
        active_collection = collection if collection is not None else _get_collection()
        result = active_collection.query(
            query_texts=[query_text],
            n_results=top_k,
            where={"feature_type": feature_type},
        )
    except Exception as exc:  # noqa: BLE001 - RAG indisponível não derruba o grafo (RF-03.5)
        logger.warning("retrieve_patterns_failed", extra={"error": str(exc)})
        return []

    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    patterns: list[PatternChunk] = []
    for document, metadata, distance in zip(documents, metadatas, distances):
        # Espaço "cosine" do ChromaDB: distance = 1 - similaridade_cosseno.
        similarity = max(0.0, 1.0 - distance)
        if similarity < similarity_threshold:
            continue
        source = (metadata or {}).get("source", "")
        patterns.append(PatternChunk(content=document, source=source, similarity=similarity))
    return patterns
