/**
 * Contratos HTTP da interface mínima (card 30) — espelham
 * `src/api/schemas.py` (Pydantic). Mantidos como um arquivo só de tipos,
 * sem lógica, para o contrato entre front e back ficar num único lugar
 * fácil de comparar com o schema Python quando um dos dois mudar.
 */

export type AnalysisStatus = "published" | "blocked" | "pending_approval" | "archived";

export interface AnalyzeRequest {
  text: string;
  /** card 43: owner/repo ou URL; vazio usa o GITHUB_REPO do servidor. */
  repo?: string;
  issue_number?: number;
}

export interface AnalyzeResponse {
  session_id: string;
  status: AnalysisStatus;
  /** card 43: repositório de fato analisado. */
  github_repo: string | null;
  risk_level: string | null;
  /** false → escalou sem avaliação (card 46); a tela mostra "não avaliado". */
  risk_assessed: boolean;
  confidence: number | null;
  human_review_required: boolean;
  published_comment_url: string | null;
  is_adversarial: boolean;
  adversarial_reason: string | null;
}

export type ApprovalDecision = "APPROVED" | "REJECTED" | "REANALYZE";

export interface ApprovalDecisionRequest {
  decision: ApprovalDecision;
  /** card 47: contexto que faltou, para a reanálise (só com REANALYZE). */
  context?: string | null;
}

export interface EvidenceSource {
  type: "code" | "rag" | "history" | "reviewer";
  ref: string;
}

export interface Impact {
  area: string;
  description: string;
  severity: string;
  evidence: string;
}

export interface Risk {
  description: string;
  severity: string;
  probability: string;
  mitigation: string | null;
}

/** card 47: parecer parcial + o que faltou, para o painel de detalhe. */
export interface EscalationDetail {
  session_id: string;
  risk_level: string | null;
  risk_assessed: boolean;
  confidence: number | null;
  threshold: number | null;
  escalation_reason: string;
  review_brief: string | null;
  requirement_summary: string | null;
  impacts: Impact[];
  risks: Risk[];
  dependencies: string[];
  recommended_tests: string[];
  evidence_sources: EvidenceSource[];
  gaps: string[];
  review_rounds: number;
  max_review_rounds: number;
}

export interface PendingApproval {
  session_id: string;
  risk_level: string | null;
  /** false → escalou sem avaliação (card 46). */
  risk_assessed: boolean;
  confidence: number | null;
  threshold: number | null;
  escalated_at: string;
  /** card 49: resumo gerado pela IA do que a mudança pede e por que escalou. */
  review_brief: string | null;
}

export interface AuditEntry {
  timestamp: string;
  session_id: string;
  decision: string;
  risk_level: string | null;
  confidence: number | null;
  threshold: number | null;
  actor: string;
  tool_authorized: string | null;
  reason: string | null;
}
