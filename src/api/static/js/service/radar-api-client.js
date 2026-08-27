/**
 * `RadarApiClient` — a única porta de saída da interface para a API do
 * RADAR (card 30). Toda chamada `fetch` da tela passa por aqui; nenhum
 * outro módulo do front toca `fetch`/`XMLHttpRequest`. Cada método devolve
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
export class RadarApiClient {
    constructor(baseUrl = "") {
        this.baseUrl = baseUrl;
    }
    async request(path, init) {
        let response;
        try {
            response = await fetch(`${this.baseUrl}${path}`, {
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
    analyze(payload) {
        return this.request("/analyze", {
            method: "POST",
            body: JSON.stringify(payload),
        });
    }
    listPendingApprovals() {
        return this.request("/approvals");
    }
    submitApprovalDecision(sessionId, decision, context) {
        return this.request(`/approvals/${encodeURIComponent(sessionId)}`, {
            method: "POST",
            body: JSON.stringify(context !== undefined ? { decision, context } : { decision }),
        });
    }
    getEscalationDetail(sessionId) {
        return this.request(`/approvals/${encodeURIComponent(sessionId)}`);
    }
    getAuditTrail(sessionId) {
        return this.request(`/audit/${encodeURIComponent(sessionId)}`);
    }
}
//# sourceMappingURL=radar-api-client.js.map