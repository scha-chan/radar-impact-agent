"""Trilha de auditoria (JSONL) — RF-09.3, segundo sinal de observabilidade
(seção 14 do PRD, card 20).

Um registro por **decisão de autonomia**: todo ponto em que o sistema age
(ou recusa agir) sem uma nova intervenção humana explícita — publicar
sozinho, escalar para revisão, bloquear por entrada adversarial, concluir
depois de uma aprovação/rejeição humana, ou arquivar por expiração de
prazo. Correlacionado ao log estruturado (card 19) pelo mesmo
`session_id`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from src import config  # noqa: F401 - carrega .env como efeito colateral do import

AuditDecision = Literal[
    "AUTO_PUBLISHED",
    "ESCALATED",
    "BLOCKED_ADVERSARIAL",
    "APPROVED_PUBLISHED",
    "REJECTED_ARCHIVED",
    "EXPIRED_ARCHIVED",
    "PUBLISH_DENIED",
]

AUDIT_LOG_PATH = os.getenv("AUDIT_LOG_PATH", "audit/trail.jsonl")


@dataclass(frozen=True)
class AuditRecord:
    session_id: str
    decision: AuditDecision
    actor: Literal["system", "human"]
    risk_level: str | None = None
    confidence: int | None = None
    threshold: int | None = None
    tool_authorized: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "decision": self.decision,
            "risk_level": self.risk_level,
            "confidence": self.confidence,
            "threshold": self.threshold,
            "actor": self.actor,
            "tool_authorized": self.tool_authorized,
        }
        if self.reason is not None:
            payload["reason"] = self.reason
        return payload


def record_audit(record: AuditRecord, *, path: str | None = None) -> None:
    """Faz append de uma linha JSON em `path` (default `AUDIT_LOG_PATH`).
    Cria o diretório se não existir — mesmo padrão de
    `publish_comment._write_dry_run_file` (card 10)."""
    target = Path(path or AUDIT_LOG_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")


def read_audit_trail(session_id: str, *, path: str | None = None) -> list[dict]:
    """Lê e filtra as entradas de uma sessão, na ordem em que foram
    gravadas — a base de dados para reconstruir uma execução real (card 21)
    e para o endpoint `GET /audit/{session_id}` (RF-09.4, card 30).
    """
    target = Path(path or AUDIT_LOG_PATH)
    if not target.exists():
        return []
    records = []
    with target.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if entry.get("session_id") == session_id:
                records.append(entry)
    return records
