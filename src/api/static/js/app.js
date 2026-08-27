/**
 * Lógica da interface mínima (card 30). Só orquestra: pega input do DOM,
 * chama `api.ts` (tipado contra `types.ts`), renderiza a resposta via
 * `dom.ts` (sem `innerHTML` com dado externo — ver `dom.ts`).
 */
import { analyzeRequirement, ApiError, getAuditTrail, listPendingApprovals, submitApprovalDecision } from "./api.js";
import { clear, el, text } from "./dom.js";
import { formatTimestamp, riskLevelClass, translateDecision, translateRiskLevel } from "./i18n.js";
const STATUS_STYLES = {
    published: "bg-rose-100 text-rose-800 border border-rose-200",
    pending_approval: "bg-amber-100 text-amber-800 border border-amber-200",
    blocked: "bg-red-100 text-red-800 border border-red-200",
    archived: "bg-stone-100 text-stone-600 border border-stone-200",
};
const STATUS_LABELS = {
    published: "publicado",
    pending_approval: "aguardando aprovação",
    blocked: "bloqueado",
    archived: "arquivado",
};
function statusBadge(status) {
    return el("span", { class: `inline-block rounded-full px-3 py-1 text-xs font-semibold ${STATUS_STYLES[status]}` }, [text(STATUS_LABELS[status])]);
}
function showMessage(message, tone = "info") {
    const box = document.querySelector("#message-box");
    if (!box)
        return;
    const toneClass = tone === "error"
        ? "bg-red-50 text-red-800 border border-red-200"
        : "bg-rose-50 text-rose-800 border border-rose-200";
    clear(box);
    box.className = `rounded-lg px-4 py-3 text-sm ${toneClass}`;
    box.append(text(message));
    box.classList.remove("hidden");
}
function hideMessage() {
    document.querySelector("#message-box")?.classList.add("hidden");
}
function renderAnalyzeResult(result) {
    const container = document.querySelector("#analyze-result");
    if (!container)
        return;
    clear(container);
    container.classList.remove("hidden");
    const rows = [
        ["session_id", result.session_id],
        ["confiança", result.confidence !== null ? String(result.confidence) : "—"],
        ["revisão humana necessária", result.human_review_required ? "sim" : "não"],
    ];
    if (result.is_adversarial && result.adversarial_reason) {
        rows.push(["motivo do bloqueio", result.adversarial_reason]);
    }
    const dl = el("dl", { class: "grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm" });
    dl.append(el("dt", { class: "font-medium text-stone-500" }, [text("risco")]), el("dd", { class: riskLevelClass(result.risk_level) }, [text(translateRiskLevel(result.risk_level))]));
    for (const [label, value] of rows) {
        dl.append(el("dt", { class: "font-medium text-stone-500" }, [text(label)]), el("dd", { class: "text-stone-800" }, [text(value)]));
    }
    const header = el("div", { class: "mb-3 flex items-center gap-3" }, [
        el("span", { class: "font-semibold text-stone-900" }, [text("Resultado")]),
        statusBadge(result.status),
    ]);
    container.append(header, dl);
    if (result.published_comment_url) {
        container.append(el("a", { href: result.published_comment_url, class: "mt-3 inline-block text-sm text-rose-700 underline" }, [
            text("Ver comentário publicado"),
        ]));
    }
    if (result.status === "pending_approval")
        void refreshApprovals();
}
async function handleAnalyzeSubmit(event) {
    event.preventDefault();
    hideMessage();
    const textInput = document.querySelector("#text");
    const issueInput = document.querySelector("#issue_number");
    const submitButton = document.querySelector("#analyze-submit");
    if (!textInput || !issueInput)
        return;
    const payload = {
        text: textInput.value,
        ...(issueInput.value ? { issue_number: Number(issueInput.value) } : {}),
    };
    submitButton?.setAttribute("disabled", "true");
    try {
        const result = await analyzeRequirement(payload);
        renderAnalyzeResult(result);
    }
    catch (error) {
        showMessage(error instanceof ApiError ? error.message : "Erro inesperado ao analisar.", "error");
    }
    finally {
        submitButton?.removeAttribute("disabled");
    }
}
function pendingApprovalCard(item) {
    const decide = async (decision) => {
        hideMessage();
        try {
            const result = await submitApprovalDecision(item.session_id, decision);
            showMessage(`Sessão ${result.session_id}: ${STATUS_LABELS[result.status]}.`);
            await refreshApprovals();
        }
        catch (error) {
            showMessage(error instanceof ApiError ? error.message : "Erro inesperado ao decidir.", "error");
        }
    };
    const approveButton = el("button", { type: "button", class: "rounded-md bg-rose-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-rose-700" }, [text("Aprovar")]);
    approveButton.addEventListener("click", () => void decide("APPROVED"));
    const rejectButton = el("button", { type: "button", class: "rounded-md bg-stone-200 px-3 py-1.5 text-sm font-medium text-stone-800 hover:bg-stone-300" }, [text("Rejeitar")]);
    rejectButton.addEventListener("click", () => void decide("REJECTED"));
    return el("div", { class: "rounded-lg border border-rose-100 bg-white p-4 shadow-sm" }, [
        el("p", { class: "font-mono text-sm text-stone-900" }, [text(item.session_id)]),
        el("p", { class: "mt-1 text-sm text-stone-600" }, [
            text(`risco: ${translateRiskLevel(item.risk_level)} · confiança: ${item.confidence ?? "—"} (threshold: ${item.threshold ?? "—"})`),
        ]),
        el("p", { class: "mt-1 text-xs text-stone-400" }, [text(`escalado em ${formatTimestamp(item.escalated_at)}`)]),
        el("div", { class: "mt-3 flex gap-2" }, [approveButton, rejectButton]),
    ]);
}
async function refreshApprovals() {
    const container = document.querySelector("#approvals-list");
    if (!container)
        return;
    clear(container);
    container.append(el("p", { class: "text-sm text-stone-400" }, [text("Carregando...")]));
    try {
        const items = await listPendingApprovals();
        clear(container);
        if (items.length === 0) {
            container.append(el("p", { class: "text-sm text-stone-400" }, [text("Nenhuma aprovação pendente.")]));
            return;
        }
        container.append(...items.map(pendingApprovalCard));
    }
    catch (error) {
        clear(container);
        showMessage(error instanceof ApiError ? error.message : "Erro ao carregar aprovações.", "error");
    }
}
function auditRow(entry) {
    const cell = (value) => el("td", { class: "border-t border-rose-100 px-3 py-2" }, [text(value)]);
    return el("tr", {}, [
        cell(formatTimestamp(entry.timestamp)),
        cell(translateDecision(entry.decision)),
        cell(entry.actor),
        cell(translateRiskLevel(entry.risk_level)),
        cell(entry.confidence !== null ? String(entry.confidence) : "—"),
        cell(entry.reason ?? entry.tool_authorized ?? "—"),
    ]);
}
async function handleLoadAudit() {
    hideMessage();
    const input = document.querySelector("#audit-session-id");
    const container = document.querySelector("#audit-result");
    if (!input || !container)
        return;
    const sessionId = input.value.trim();
    if (!sessionId)
        return;
    clear(container);
    try {
        const entries = await getAuditTrail(sessionId);
        const table = el("table", { class: "w-full border-collapse text-sm" }, [
            el("thead", {}, [
                el("tr", { class: "text-left text-stone-500" }, [
                    el("th", { class: "px-3 py-2" }, [text("Timestamp")]),
                    el("th", { class: "px-3 py-2" }, [text("Decisão")]),
                    el("th", { class: "px-3 py-2" }, [text("Ator")]),
                    el("th", { class: "px-3 py-2" }, [text("Risco")]),
                    el("th", { class: "px-3 py-2" }, [text("Confiança")]),
                    el("th", { class: "px-3 py-2" }, [text("Detalhe")]),
                ]),
            ]),
            el("tbody", {}, entries.map(auditRow)),
        ]);
        container.append(table);
    }
    catch (error) {
        if (error instanceof ApiError && error.status === 404) {
            container.append(el("p", { class: "text-sm text-stone-400" }, [text("Nenhuma auditoria encontrada para essa sessão.")]));
        }
        else {
            showMessage(error instanceof ApiError ? error.message : "Erro ao carregar auditoria.", "error");
        }
    }
}
function init() {
    document.querySelector("#analyze-form")?.addEventListener("submit", (event) => void handleAnalyzeSubmit(event));
    document.querySelector("#refresh-approvals")?.addEventListener("click", () => void refreshApprovals());
    document.querySelector("#load-audit")?.addEventListener("click", () => void handleLoadAudit());
}
document.addEventListener("DOMContentLoaded", init);
//# sourceMappingURL=app.js.map