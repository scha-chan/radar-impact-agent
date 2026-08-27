"""Portão de qualidade RNF-10 (card 37): mutation score acima de 60% em
`src/domain/` e `src/governance/`, medido com `mutmut`.

Separado do comando `mutmut run` porque ele não expõe uma opção própria de
"falhar se o score ficar abaixo de X" — o score (`killed / total`) é
calculado aqui, a partir de `mutants/mutmut-cicd-stats.json` (gerado por
`mutmut export_cicd_stats`), e usado para decidir o código de saída do job
de CI (`.github/workflows/ci.yml`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_MIN_SCORE = 60.0


def compute_mutation_score(stats: dict) -> float:
    """`killed / total` — conservador de propósito: um mutante `no_tests`
    (linha sem nenhum teste passando por cima) conta contra o score, não é
    ignorado. É exatamente a lacuna que RNF-10 quer expor além da
    cobertura de linha — um `no_tests` já teria zerado a cobertura, mas um
    mutante `survived` (linha coberta, mas nenhum teste percebe a
    mutação) só aparece aqui, nunca no relatório de cobertura."""
    total = stats["total"]
    if total == 0:
        return 100.0
    return 100.0 * stats["killed"] / total


def _format_report(stats: dict, score: float) -> str:
    return (
        f"Mutation score: {score:.1f}% "
        f"(killed={stats['killed']}, survived={stats['survived']}, "
        f"no_tests={stats['no_tests']}, timeout={stats['timeout']}, "
        f"suspicious={stats['suspicious']}, total={stats['total']})"
    )


def check_mutation_score(stats_path: str | Path, *, min_score: float = DEFAULT_MIN_SCORE) -> bool:
    """Devolve `True` se o score >= `min_score`, imprimindo o relatório."""
    stats = json.loads(Path(stats_path).read_text(encoding="utf-8"))
    score = compute_mutation_score(stats)
    print(_format_report(stats, score))
    if score < min_score:
        print(f"FALHOU: score abaixo do mínimo exigido ({min_score}%) — RNF-10.")
        return False
    print(f"OK: score >= {min_score}% (RNF-10).")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stats_path", help="caminho de mutmut-cicd-stats.json")
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    args = parser.parse_args(argv)

    return 0 if check_mutation_score(args.stats_path, min_score=args.min_score) else 1


if __name__ == "__main__":
    sys.exit(main())
