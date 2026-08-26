import pytest
from langchain_ollama import ChatOllama

from src.graph import llm


def test_build_chat_model_returns_chat_ollama_configured_from_module_constants(monkeypatch):
    monkeypatch.setattr(llm, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(llm, "LLM_MODEL", "mistral")
    monkeypatch.setattr(llm, "OLLAMA_BASE_URL", "http://localhost:11434")

    model = llm.build_chat_model(temperature=0.2)

    assert isinstance(model, ChatOllama)
    assert model.model == "mistral"
    assert model.base_url == "http://localhost:11434"


def test_build_chat_model_raises_for_unsupported_provider(monkeypatch):
    monkeypatch.setattr(llm, "LLM_PROVIDER", "openai")

    with pytest.raises(NotImplementedError, match="openai"):
        llm.build_chat_model()
