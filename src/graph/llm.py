"""Fábrica do cliente LLM usado pelos nodes agênticos do grafo.

Provedor local (Ollama) por padrão — sem custo de API, sem chave, roda
inteiramente na máquina do avaliador. Trocável por outro provedor via
`LLM_PROVIDER`/`LLM_MODEL` (seção 18 do PRD) sem tocar nos nodes que o
consomem — eles só chamam `build_chat_model()`.
"""

from __future__ import annotations

import os

from langchain_ollama import ChatOllama

from src import config  # noqa: F401 - carrega .env como efeito colateral do import

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
LLM_MODEL = os.getenv("LLM_MODEL", "mistral")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def build_chat_model(*, temperature: float = 0.0):
    if LLM_PROVIDER != "ollama":
        raise NotImplementedError(
            f"LLM_PROVIDER={LLM_PROVIDER!r} ainda não é suportado — só 'ollama' "
            "está implementado (ver seção 18 do PRD)."
        )
    return ChatOllama(model=LLM_MODEL, base_url=OLLAMA_BASE_URL, temperature=temperature)
