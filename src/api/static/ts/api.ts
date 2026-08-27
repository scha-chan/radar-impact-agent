/**
 * Cliente HTTP tipado para a API do RADAR (card 30). Cada função devolve
 * o tipo exato de `types.ts` ou lança `ApiError` — quem chama nunca
 * precisa checar `response.ok` nem fazer cast manual do JSON.
 */

import type {
  AnalyzeRequest,
  AnalyzeResponse,
  ApprovalDecision,
  AuditEntry,
  EscalationDetail,
  PendingApproval,
} from "./types.js";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError("Falha de rede ao contatar a API do RADAR.", 0);
  }

  if (!response.ok) {
    const detail = await response
      .json()
      .then((body: { detail?: string }) => body.detail)
      .catch(() => undefined);
    throw new ApiError(detail ?? `Erro ${response.status} ao chamar ${path}.`, response.status);
  }

  return (await response.json()) as T;
}

export function analyzeRequirement(payload: AnalyzeRequest): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>("/analyze", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listPendingApprovals(): Promise<PendingApproval[]> {
  return request<PendingApproval[]>("/approvals");
}

export function submitApprovalDecision(
  sessionId: string,
  decision: ApprovalDecision,
  context?: string,
): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>(`/approvals/${encodeURIComponent(sessionId)}`, {
    method: "POST",
    body: JSON.stringify(context !== undefined ? { decision, context } : { decision }),
  });
}

export function getEscalationDetail(sessionId: string): Promise<EscalationDetail> {
  return request<EscalationDetail>(`/approvals/${encodeURIComponent(sessionId)}`);
}

export function getAuditTrail(sessionId: string): Promise<AuditEntry[]> {
  return request<AuditEntry[]>(`/audit/${encodeURIComponent(sessionId)}`);
}
