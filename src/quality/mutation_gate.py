"""Portão de qualidade RNF-10 (card 37): mutation score acima de 60% em
`src/domain/` e `src/governance/`, medido com `mutmut` (2.5.1 — a série
3.x não suporta o layout de import deste projeto, `from src.xxx import
...`; ver `docs/evidencias/card-37-mutation-testing.md`).

Lê o relatório JUnit XML (`mutmut junitxml`) — cada `<testcase>` é um
mutante; um `<failure>`/`<error>` significa que ele sobreviveu (nenhum
teste percebeu a mutação) ou deu timeout. `mutmut run` não expõe uma
opção própria de "falhar se o score ficar abaixo de X"; esse cálculo e a
decisão do código de saída do job de CI (`.github/workflows/ci.yml`)
ficam aqui.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULT_MIN_SCORE = 60.0


def compute_mutation_score(total: int, not_killed: int) -> float:
    """`(total - not_killed) / total` — `not_killed` conta sobreviventes
    e timeouts, os dois casos em que a mutação passou despercebida."""
    if total == 0:
        return 100.0
    return 100.0 * (total - not_killed) / total


def parse_junitxml(path: str | Path) -> tuple[int, int]:
    """`mutmut junitxml` agrega os totais no elemento raiz `<testsuites>`
    — não é preciso iterar `<testcase>` um a um."""
    root = ET.parse(path).getroot()
    total = int(root.get("tests", 0))
    not_killed = int(root.get("failures", 0)) + int(root.get("errors", 0))
    return total, not_killed


def _format_report(total: int, not_killed: int, score: float) -> str:
    return (
        f"Mutation score: {score:.1f}% "
        f"(killed={total - not_killed}, survived_or_timeout={not_killed}, total={total})"
    )


def check_mutation_score(
    junitxml_path: str | Path, *, min_score: float = DEFAULT_MIN_SCORE
) -> bool:
    """Devolve `True` se o score >= `min_score`, imprimindo o relatório."""
    total, not_killed = parse_junitxml(junitxml_path)
    score = compute_mutation_score(total, not_killed)
    print(_format_report(total, not_killed, score))
    if score < min_score:
        print(f"FALHOU: score abaixo do mínimo exigido ({min_score}%) — RNF-10.")
        return False
    print(f"OK: score >= {min_score}% (RNF-10).")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("junitxml_path", help="caminho do relatório gerado por `mutmut junitxml`")
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    args = parser.parse_args(argv)

    return 0 if check_mutation_score(args.junitxml_path, min_score=args.min_score) else 1


if __name__ == "__main__":
    sys.exit(main())
