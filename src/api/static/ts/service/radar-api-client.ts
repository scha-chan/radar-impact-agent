/**
 * `RadarApiClient` — a única porta de saída da interface para a API do
 * RADAR (card 30). Toda chamada `fetch` da tela passa por aqui; nenhum
 * outro módulo do front toca `fetch`/`XMLHttpRequest`. Cada método devolve
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
} from "../types.js";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class RadarApiClient {
  constructor(private readonly baseUrl: string = "") {}

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}${path}`, {
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

  analyze(payload: AnalyzeRequest): Promise<AnalyzeResponse> {
    return this.request<AnalyzeResponse>("/analyze", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  listPendingApprovals(): Promise<PendingApproval[]> {
    return this.request<PendingApproval[]>("/approvals");
  }

  submitApprovalDecision(
    sessionId: string,
    decision: ApprovalDecision,
    context?: string,
  ): Promise<AnalyzeResponse> {
    return this.request<AnalyzeResponse>(`/approvals/${encodeURIComponent(sessionId)}`, {
      method: "POST",
      body: JSON.stringify(context !== undefined ? { decision, context } : { decision }),
    });
  }

  getEscalationDetail(sessionId: string): Promise<EscalationDetail> {
    return this.request<EscalationDetail>(`/approvals/${encodeURIComponent(sessionId)}`);
  }

  getAuditTrail(sessionId: string): Promise<AuditEntry[]> {
    return this.request<AuditEntry[]>(`/audit/${encodeURIComponent(sessionId)}`);
  }
}
