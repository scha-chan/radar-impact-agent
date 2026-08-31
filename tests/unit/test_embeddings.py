from src.rag.embeddings import OllamaEmbeddingFunction, build_embedding_function


def test_ollama_embedding_function_name_reflects_configured_model():
    ef = OllamaEmbeddingFunction(model="nomic-embed-text", base_url="http://localhost:11434")

    assert ef.name() == "ollama:nomic-embed-text"


def test_build_embedding_function_returns_an_ollama_embedding_function():
    ef = build_embedding_function()

    assert isinstance(ef, OllamaEmbeddingFunction)
