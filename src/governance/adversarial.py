"""Detector adversarial — RF-06.3, seção 13 do PRD (card 18, cenário 3).

Três camadas de defesa contra instrução embutida no texto do requisito:

1. **Delimitação estrutural** — já existe desde o card 06: o texto do
   requisito entra no prompt dentro de um bloco delimitado (`\"\"\"..\"\"\"`),
   com instrução de sistema afirmando que é dado, não comando
   (`src/graph/prompts.py`).
2. **Detecção** — este módulo: padrões conhecidos (determinístico, sem
   custo de LLM) combinados com uma checagem por LLM quando os padrões não
   encontram nada.
3. **Contenção arquitetural** — já garantida estruturalmente desde o card
   02/04: `score_risk` é Python puro, o LLM nunca decide `risk_level` nem o
   threshold de escalação. Nada neste módulo muda isso; as duas primeiras
   camadas só reduzem o ruído que chegaria a `analyze_impact`. É a terceira
   camada que sustenta a garantia de verdade (seção 13 do PRD).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(frozen=True)
class AdversarialCheck:
    is_adversarial: bool
    reason: str | None


class AdversarialVerdict(BaseModel):
    """Saída estruturada da checagem por LLM (camada 2)."""

    is_adversarial: bool
    reason: str


# Imperativos dirigidos ao agente, tentativas de redefinir regras, pedidos
# de forçar classificação/aprovação — os três padrões que a seção 13 do
# PRD nomeia explicitamente. Cobre português e inglês (RF-01.1 aceita os
# dois idiomas).
_PATTERN_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"ignor[ae]\s+(as\s+)?regras", re.IGNORECASE),
        "pede para ignorar as regras/controles de segurança",
    ),
    (
        re.compile(r"desconsider[ae]\s+(as\s+)?(regras|instru[çc][õo]es)", re.IGNORECASE),
        "pede para desconsiderar regras ou instruções do sistema",
    ),
    (
        re.compile(r"ignore\s+(the\s+)?(rules|instructions|previous)", re.IGNORECASE),
        "asks to ignore rules/instructions",
    ),
    (
        re.compile(r"disregard\s+(the\s+)?(rules|instructions|previous)", re.IGNORECASE),
        "asks to disregard rules/instructions",
    ),
    (
        re.compile(r"publiqu[ae]\s+[^.]*sem\s+revis[ãa]o", re.IGNORECASE),
        "pede para publicar sem revisão humana",
    ),
    (
        re.compile(r"publish\s+[^.]*without\s+(any\s+)?review", re.IGNORECASE),
        "asks to publish without human review",
    ),
    (
        re.compile(r"classifiqu[ae]\s+[^.]*risco\s+baixo", re.IGNORECASE),
        "pede para forçar a classificação de risco",
    ),
    (
        re.compile(r"considere?\s+que\s+qualquer\s+usu[áa]rio", re.IGNORECASE),
        "tenta redefinir regra de autorização/acesso",
    ),
    (
        re.compile(
            r"you\s+are\s+now\s+a?n?\s*[\w\s]*(no\s+restrictions|unrestricted)", re.IGNORECASE
        ),
        "tenta redefinir o papel/restrições do agente",
    ),
]


def detect_by_pattern(text: str) -> AdversarialCheck:
    """Camada 1: determinística, sem custo de LLM. Roda antes da camada 2
    para casos óbvios não gastarem uma chamada de modelo."""
    for pattern, reason in _PATTERN_RULES:
        match = pattern.search(text)
        if match:
            return AdversarialCheck(is_adversarial=True, reason=f'{reason} ("{match.group(0)}")')
    return AdversarialCheck(is_adversarial=False, reason=None)


def render_block_message(reason: str) -> str:
    """Formato do cenário 3 (seção 12 do PRD) — usado pelo node `block`
    para o log estruturado e, futuramente, pela API (card 30) para a
    resposta ao usuário."""
    return (
        "ENTRADA POTENCIALMENTE ADVERSARIAL\n\n"
        f"{reason}\n\n"
        "Ação: BLOQUEADA\n"
        "Motivo: as regras da aplicação têm precedência sobre instruções "
        "presentes no conteúdo analisado."
    )
