/**
 * Cliente HTTP tipado para a API do RADAR (card 30). Cada função devolve
 * o tipo exato de `types.ts` ou lança `ApiError` — quem chama nunca
 * precisa checar `response.ok` nem fazer cast manual do JSON.
 */
export class ApiError extends Error {
    constructor(message, status) {
        super(message);
        this.status = status;
        this.name = "ApiError";
    }
}
async function request(path, init) {
    let response;
    try {
        response = await fetch(path, {
            headers: { "Content-Type": "application/json" },
            ...init,
        });
    }
    catch {
        throw new ApiError("Falha de rede ao contatar a API do RADAR.", 0);
    }
    if (!response.ok) {
        const detail = await response
            .json()
            .then((body) => body.detail)
            .catch(() => undefined);
        throw new ApiError(detail ?? `Erro ${response.status} ao chamar ${path}.`, response.status);
    }
    return (await response.json());
}
export function analyzeRequirement(payload) {
    return request("/analyze", {
        method: "POST",
        body: JSON.stringify(payload),
    });
}
export function listPendingApprovals() {
    return request("/approvals");
}
export function submitApprovalDecision(sessionId, decision, context) {
    return request(`/approvals/${encodeURIComponent(sessionId)}`, {
        method: "POST",
        body: JSON.stringify(context !== undefined ? { decision, context } : { decision }),
    });
}
export function getEscalationDetail(sessionId) {
    return request(`/approvals/${encodeURIComponent(sessionId)}`);
}
export function getAuditTrail(sessionId) {
    return request(`/audit/${encodeURIComponent(sessionId)}`);
}
//# sourceMappingURL=api.js.map