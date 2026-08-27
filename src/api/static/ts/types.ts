/**
 * Contratos HTTP da interface mínima (card 30) — espelham
 * `src/api/schemas.py` (Pydantic). Mantidos como um arquivo só de tipos,
 * sem lógica, para o contrato entre front e back ficar num único lugar
 * fácil de comparar com o schema Python quando um dos dois mudar.
 */

export type AnalysisStatus = "published" | "blocked" | "pending_approval" | "archived";

export interface AnalyzeRequest {
  text: string;
  issue_number?: number;
}

export interface AnalyzeResponse {
  session_id: string;
  status: AnalysisStatus;
  risk_level: string | null;
  /** false → escalou sem avaliação (card 46); a tela mostra "não avaliado". */
  risk_assessed: boolean;
  confidence: number | null;
  human_review_required: boolean;
  published_comment_url: string | null;
  is_adversarial: boolean;
  adversarial_reason: string | null;
}

export type ApprovalDecision = "APPROVED" | "REJECTED";

export interface ApprovalDecisionRequest {
  decision: ApprovalDecision;
}

export interface PendingApproval {
  session_id: string;
  risk_level: string | null;
  /** false → escalou sem avaliação (card 46). */
  risk_assessed: boolean;
  confidence: number | null;
  threshold: number | null;
  escalated_at: string;
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
