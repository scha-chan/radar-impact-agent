from pathlib import Path

from src.rag.corpus import load_corpus, parse_file

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge"

_SAMPLE = """# Padrões de impacto — login

## Autenticação e sessão

**Área:** authentication
**Descrição:** Mudanças no fluxo de login afetam sessões.
**Riscos típicos:** invalidação acidental de sessões ativas.
**Dependências comuns:** serviço de sessão.
**Testes recomendados:** login válido, expiração de sessão.

## Recuperação de senha

**Área:** password_recovery
**Descrição:** Login e recuperação de senha compartilham dependências.
**Riscos típicos:** token de recuperação reutilizável.
**Dependências comuns:** serviço de e-mail.
**Testes recomendados:** solicitação de recuperação.
"""


def test_parse_file_extracts_one_document_per_section(tmp_path):
    path = tmp_path / "login.md"
    path.write_text(_SAMPLE, encoding="utf-8")

    documents = parse_file(path)

    assert len(documents) == 2
    first, second = documents
    assert first.feature_type == "login"
    assert first.pattern_name == "Autenticação e sessão"
    assert first.area == "authentication"
    assert second.pattern_name == "Recuperação de senha"
    assert second.area == "password_recovery"


def test_parse_file_content_includes_pattern_name_and_body(tmp_path):
    path = tmp_path / "login.md"
    path.write_text(_SAMPLE, encoding="utf-8")

    document = parse_file(path)[0]

    assert document.content.startswith("Autenticação e sessão")
    assert "invalidação acidental de sessões ativas" in document.content


def test_parse_file_source_is_a_stable_slug(tmp_path):
    path = tmp_path / "login.md"
    path.write_text(_SAMPLE, encoding="utf-8")

    document = parse_file(path)[0]

    assert document.source == "knowledge/login.md#autenticação-e-sessão"


def test_load_corpus_skips_readme(tmp_path):
    (tmp_path / "README.md").write_text("# Corpus\n\nNão é conteúdo.", encoding="utf-8")
    (tmp_path / "login.md").write_text(_SAMPLE, encoding="utf-8")

    documents = load_corpus(tmp_path)

    assert len(documents) == 2
    assert all(doc.feature_type == "login" for doc in documents)


def test_load_corpus_over_real_knowledge_dir_has_at_least_50_chunks():
    documents = load_corpus(KNOWLEDGE_DIR)

    assert len(documents) >= 50
    feature_types = {doc.feature_type for doc in documents}
    assert "outro" not in feature_types
    assert "login" in feature_types
    assert all(doc.area for doc in documents), "todo padrão real deve ter Área preenchida"


def test_parse_file_area_is_empty_string_when_field_is_missing(tmp_path):
    path = tmp_path / "login.md"
    path.write_text(
        "## Padrão sem área\n\n**Descrição:** sem o campo Área.\n",
        encoding="utf-8",
    )

    document = parse_file(path)[0]

    assert document.area == ""
