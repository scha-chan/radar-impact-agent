"""Fábrica da função de embedding usada pelo índice vetorial (ChromaDB).

Mesmo princípio de `src/graph/llm.py`: Ollama local por padrão (sem custo de
API, sem chave), isolado atrás de `build_embedding_function()` para trocar de
provedor/modelo no futuro sem tocar em `ingest.py`/`retriever.py`.
"""

from __future__ import annotations

import os

from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from langchain_ollama import OllamaEmbeddings

from src import config  # noqa: F401 - carrega .env como efeito colateral do import

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")


class OllamaEmbeddingFunction(EmbeddingFunction):
    """Adapta `OllamaEmbeddings` (langchain) ao protocolo `EmbeddingFunction`
    do ChromaDB (`__call__(Documents) -> Embeddings`)."""

    def __init__(self, model: str = OLLAMA_EMBED_MODEL, base_url: str = OLLAMA_BASE_URL):
        self._model = model
        self._base_url = base_url
        self._client = OllamaEmbeddings(model=model, base_url=base_url)

    def __call__(self, input: Documents) -> Embeddings:  # noqa: A002 - nome exigido pelo protocolo
        return self._client.embed_documents(list(input))

    def name(self) -> str:
        return f"ollama:{self._model}"


def build_embedding_function() -> EmbeddingFunction:
    return OllamaEmbeddingFunction()
