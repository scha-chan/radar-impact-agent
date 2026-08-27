/**
 * Tradução e formatação de exibição — a API (`src/api/schemas.py`)
 * devolve `risk_level`/`decision` em inglês (mesmos literais do backend,
 * `src/domain/risk.py`/`src/observability/audit.py`) e timestamps em
 * ISO-8601 UTC (`datetime.isoformat()`). Este módulo só traduz para
 * exibição — os valores enviados de volta à API (`decision` em
 * `ApprovalDecisionRequest`) continuam os literais originais, nunca os
 * traduzidos.
 */

const RISK_LEVEL_LABELS: Record<string, string> = {
  LOW: "Baixo",
  MEDIUM: "Médio",
  HIGH: "Alto",
  CRITICAL: "Crítico",
};

export function translateRiskLevel(level: string | null): string {
  if (level === null) return "—";
  return RISK_LEVEL_LABELS[level] ?? level;
}

const DECISION_LABELS: Record<string, string> = {
  ESCALATED: "Escalado para aprovação",
  AUTO_PUBLISHED: "Publicado automaticamente",
  APPROVED_PUBLISHED: "Aprovado e publicado",
  REJECTED_ARCHIVED: "Rejeitado e arquivado",
  EXPIRED_ARCHIVED: "Expirado e arquivado",
  BLOCKED_ADVERSARIAL: "Bloqueado (entrada adversarial)",
  PUBLISH_DENIED: "Publicação negada",
};

export function translateDecision(decision: string): string {
  return DECISION_LABELS[decision] ?? decision;
}

/**
 * `DD/MM/AAAA hh:mm:ss` no fuso horário local do navegador — os
 * timestamps chegam em UTC (backend), converter para local é o
 * comportamento esperado numa UI; só o formato de exibição muda.
 */
export function formatTimestamp(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  if (Number.isNaN(date.getTime())) return isoTimestamp;

  const pad = (value: number): string => String(value).padStart(2, "0");
  const day = pad(date.getDate());
  const month = pad(date.getMonth() + 1);
  const year = date.getFullYear();
  const hours = pad(date.getHours());
  const minutes = pad(date.getMinutes());
  const seconds = pad(date.getSeconds());

  return `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`;
}
