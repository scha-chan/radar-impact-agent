"""Parsing do corpus de padrões de impacto (`knowledge/*.md`) em chunks.

Cada arquivo é um tipo de feature; cada seção `##` dentro dele é um padrão de
impacto com o schema fixo documentado em `knowledge/README.md` (Área,
Descrição, Riscos típicos, Dependências comuns, Testes recomendados). Este
módulo só faz parsing — puro, sem dependência de ChromaDB ou embeddings —
para o card 13 (ingestão) e os testes poderem tratar essa etapa isoladamente
do índice vetorial.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_PATTERN_HEADER_RE = re.compile(r"^## (.+)$", re.MULTILINE)
_FIELD_RE = re.compile(r"^\*\*(.+?):\*\*\s*(.*)$")


@dataclass(frozen=True)
class PatternDocument:
    """Um padrão de impacto pronto para virar um chunk do índice vetorial."""

    feature_type: str
    pattern_name: str
    area: str
    content: str
    source: str


def _slugify(text: str) -> str:
    slug = text.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    return re.sub(r"[\s_]+", "-", slug)


def _extract_field(body: str, field_name: str) -> str:
    for line in body.splitlines():
        match = _FIELD_RE.match(line.strip())
        if match and match.group(1).strip() == field_name:
            return match.group(2).strip()
    return ""


def parse_file(path: Path) -> list[PatternDocument]:
    """Extrai um `PatternDocument` por seção `##` do arquivo.

    `feature_type` vem do nome do arquivo (`login.md` -> `login`) — os
    arquivos em `knowledge/` são nomeados exatamente como os valores
    concretos de `FeatureType` (`src/graph/state.py`).
    """
    feature_type = path.stem
    text = path.read_text(encoding="utf-8")
    headers = list(_PATTERN_HEADER_RE.finditer(text))

    documents = []
    for i, header in enumerate(headers):
        pattern_name = header.group(1).strip()
        start = header.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        body = text[start:end].strip()

        area = _extract_field(body, "Área")
        # O nome do padrão entra no texto embedado — a similaridade semântica
        # também deve responder ao título ("Segundo fator de autenticação"),
        # não só ao corpo dos campos.
        content = f"{pattern_name}\n\n{body}"
        source = f"knowledge/{feature_type}.md#{_slugify(pattern_name)}"

        documents.append(
            PatternDocument(
                feature_type=feature_type,
                pattern_name=pattern_name,
                area=area,
                content=content,
                source=source,
            )
        )
    return documents


def load_corpus(knowledge_dir: Path) -> list[PatternDocument]:
    """Carrega todos os padrões de `knowledge_dir`, um arquivo por tipo de
    feature. `README.md` é documentação do corpus, não conteúdo dele."""
    documents: list[PatternDocument] = []
    for path in sorted(knowledge_dir.glob("*.md")):
        if path.stem.lower() == "readme":
            continue
        documents.extend(parse_file(path))
    return documents
