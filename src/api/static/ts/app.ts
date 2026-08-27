/**
 * Lógica da interface mínima (card 30). Só orquestra: pega input do DOM,
 * chama a API pelo `RadarApiClient` (única porta de saída, `service/`),
 * renderiza via `dom.ts` (sem `innerHTML` com dado externo). Padrões de
 * tela que se repetem (pegar elemento, mensagem de erro, botão ocupado,
 * faixa de mensagem) ficam em `service/util-service.ts`.
 */

import { clear, el, text } from "./dom.js";
import {
  formatTimestamp,
  riskDisplayClass,
  riskDisplayLabel,
  translateDecision,
  translateRiskLevel,
} from "./i18n.js";
import { RadarApiClient } from "./service/radar-api-client.js";
import { MessageBox, UtilService } from "./service/util-service.js";
import type {
  AnalysisStatus,
  AnalyzeResponse,
  ApprovalDecision,
  AuditEntry,
  EscalationDetail,
  PendingApproval,
} from "./types.js";

const api = new RadarApiClient();

const STATUS_STYLES: Record<AnalysisStatus, string> = {
  published: "bg-rose-100 text-rose-800 border border-rose-200",
  pending_approval: "bg-amber-100 text-amber-800 border border-amber-200",
  blocked: "bg-red-100 text-red-800 border border-red-200",
  archived: "bg-stone-100 text-stone-600 border border-stone-200",
};

const STATUS_LABELS: Record<AnalysisStatus, string> = {
  published: "publicado",
  pending_approval: "aguardando aprovação",
  blocked: "bloqueado",
  archived: "arquivado",
};

function statusBadge(status: AnalysisStatus): HTMLSpanElement {
  return el(
    "span",
    { class: `inline-block rounded-full px-3 py-1 text-xs font-semibold ${STATUS_STYLES[status]}` },
    [text(STATUS_LABELS[status])],
  );
}

function renderAnalyzeResult(result: AnalyzeResponse): void {
  const container = UtilService.byId<HTMLDivElement>("analyze-result");
  if (!container) return;
  clear(container);
  container.classList.remove("hidden");

  const rows: Array<[string, string]> = [
    ["session_id", result.session_id],
    ["confiança", result.confidence !== null ? String(result.confidence) : "—"],
    ["revisão humana necessária", result.human_review_required ? "sim" : "não"],
  ];
  if (result.is_adversarial && result.adversarial_reason) {
    rows.push(["motivo do bloqueio", result.adversarial_reason]);
  }

  const dl = el("dl", { class: "grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm" });
  dl.append(
    el("dt", { class: "font-medium text-stone-500" }, [text("risco")]),
    el("dd", { class: riskDisplayClass(result.risk_level, result.risk_assessed) }, [
      text(riskDisplayLabel(result.risk_level, result.risk_assessed)),
    ]),
  );
  for (const [label, value] of rows) {
    dl.append(
      el("dt", { class: "font-medium text-stone-500" }, [text(label)]),
      el("dd", { class: "text-stone-800" }, [text(value)]),
    );
  }

  const header = el("div", { class: "mb-3 flex items-center gap-3" }, [
    el("span", { class: "font-semibold text-stone-900" }, [text("Resultado")]),
    statusBadge(result.status),
  ]);

  container.append(header, dl);

  if (result.published_comment_url) {
    container.append(
      el(
        "a",
        {
          href: result.published_comment_url,
          class: "mt-3 inline-block text-sm text-rose-700 underline",
        },
        [text("Ver comentário publicado")],
      ),
    );
  }

  if (result.status === "pending_approval") void refreshApprovals();
}

async function handleAnalyzeSubmit(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  MessageBox.hide();

  const textInput = UtilService.byId<HTMLTextAreaElement>("text");
  const issueInput = UtilService.byId<HTMLInputElement>("issue_number");
  const submitButton = UtilService.byId<HTMLButtonElement>("analyze-submit");
  if (!textInput || !issueInput || !submitButton) return;

  const payload = {
    text: textInput.value,
    ...(issueInput.value ? { issue_number: Number(issueInput.value) } : {}),
  };

  try {
    const result = await UtilService.busy(submitButton, () => api.analyze(payload));
    renderAnalyzeResult(result);
  } catch (error) {
    MessageBox.show(UtilService.errorMessage(error, "Erro inesperado ao analisar."), "error");
  }
}

/** card 49: o resumo gerado pela IA — o que o revisor lê primeiro. */
function reviewBriefBlock(brief: string | null): HTMLElement | null {
  if (!brief) return null;
  const paragraphs = brief.split("\n\n").filter((p) => p.trim() !== "");
  return el(
    "div",
    { class: "mt-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-stone-800" },
    paragraphs.map((p) => el("p", { class: "mt-1 first:mt-0" }, [text(p)])),
  );
}

function bulletList(title: string, items: string[]): HTMLElement {
  return el("div", { class: "mt-2" }, [
    el("p", { class: "text-xs font-semibold uppercase tracking-wide text-stone-500" }, [
      text(title),
    ]),
    items.length === 0
      ? el("p", { class: "text-sm text-stone-400" }, [text("—")])
      : el(
          "ul",
          { class: "ml-4 list-disc text-sm text-stone-700" },
          items.map((line) => el("li", {}, [text(line)])),
        ),
  ]);
}

function renderEscalationDetail(detail: EscalationDetail): HTMLElement {
  const children: Array<Node | string> = [];
  const brief = reviewBriefBlock(detail.review_brief);
  if (brief) children.push(brief);
  children.push(
    el("p", { class: "mt-2 text-stone-700" }, [
      text(
        `Por que escalou: ${detail.escalation_reason}. Rodadas de reanálise: ${detail.review_rounds}/${detail.max_review_rounds}.`,
      ),
    ]),
  );
  return el("div", { class: "mt-3 rounded-md bg-stone-50 p-3 text-sm" }, [
    ...children,
    bulletList("O que faltou", detail.gaps),
    bulletList(
      "Impactos",
      detail.impacts.map(
        (i) => `[${i.severity}] ${i.area}: ${i.description} (evidência: ${i.evidence})`,
      ),
    ),
    bulletList(
      "Riscos",
      detail.risks.map(
        (r) =>
          `[${r.severity}/${r.probability}] ${r.description}` +
          (r.mitigation ? ` — mitigação: ${r.mitigation}` : ""),
      ),
    ),
    bulletList("Dependências", detail.dependencies),
    bulletList("Testes recomendados", detail.recommended_tests),
    bulletList(
      "Evidência coletada",
      detail.evidence_sources.map((e) => `[${e.type}] ${e.ref}`),
    ),
  ]);
}

function pendingApprovalCard(item: PendingApproval): HTMLDivElement {
  const resultBox = el("p", { class: "mt-3 hidden text-sm" });
  const detailSlot = el("div", {});
  const contextInput = el("textarea", {
    rows: "2",
    placeholder: "Contexto adicional para reanálise (opcional)",
    class:
      "mt-3 w-full rounded-md border border-stone-300 p-2 text-sm focus:border-rose-500 focus:outline-none focus:ring-1 focus:ring-rose-500",
  }) as HTMLTextAreaElement;

  const buttons: HTMLButtonElement[] = [];
  const setBusy = (busy: boolean, active?: HTMLButtonElement, label?: string): void => {
    for (const b of buttons) b.disabled = busy;
    contextInput.disabled = busy;
    if (active && label !== undefined) active.textContent = busy ? "…" : label;
  };
  const showResult = (msg: string, ok: boolean): void => {
    resultBox.className = `mt-3 text-sm ${ok ? "text-emerald-700" : "text-red-700"}`;
    resultBox.textContent = msg;
  };

  const act =
    (button: HTMLButtonElement, label: string, decision: ApprovalDecision) =>
    async (): Promise<void> => {
      MessageBox.hide();
      showResult("processando…", true);
      setBusy(true, button, label);
      try {
        const result =
          decision === "REANALYZE"
            ? await api.submitApprovalDecision(item.session_id, decision, contextInput.value)
            : await api.submitApprovalDecision(item.session_id, decision);
        const done =
          decision === "REANALYZE" && result.status === "pending_approval"
            ? "Reanálise concluída — parecer atualizado, ainda aguardando decisão."
            : `Sessão ${result.session_id}: ${STATUS_LABELS[result.status]}.`;
        // O card some/recarrega no refresh; a mensagem no topo persiste.
        showResult(done, true);
        MessageBox.show(done);
        contextInput.value = "";
        detailSlot.replaceChildren();
        await refreshApprovals();
      } catch (error) {
        const msg = UtilService.errorMessage(error, "Erro inesperado ao decidir.");
        showResult(msg, false);
        MessageBox.show(msg, "error");
        if (UtilService.isNotFound(error)) await refreshApprovals();
      } finally {
        setBusy(false, button, label);
      }
    };

  const mkButton = (label: string, cls: string, decision: ApprovalDecision): HTMLButtonElement => {
    const b = el("button", { type: "button", class: cls }, [text(label)]) as HTMLButtonElement;
    b.addEventListener("click", () => void act(b, label, decision)());
    buttons.push(b);
    return b;
  };

  const approveButton = mkButton(
    "Aprovar",
    "rounded-md bg-rose-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-rose-700 disabled:opacity-50",
    "APPROVED",
  );
  const rejectButton = mkButton(
    "Rejeitar",
    "rounded-md bg-stone-200 px-3 py-1.5 text-sm font-medium text-stone-800 hover:bg-stone-300 disabled:opacity-50",
    "REJECTED",
  );
  const reanalyzeButton = mkButton(
    "Reanalisar",
    "rounded-md border border-rose-300 px-3 py-1.5 text-sm font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-50",
    "REANALYZE",
  );

  const detailButton = el(
    "button",
    { type: "button", class: "text-xs text-rose-700 underline disabled:opacity-50" },
    [text("Ver detalhe")],
  ) as HTMLButtonElement;
  detailButton.addEventListener("click", () => {
    void (async (): Promise<void> => {
      if (detailSlot.childElementCount > 0) {
        detailSlot.replaceChildren();
        return;
      }
      detailButton.disabled = true;
      try {
        const detail = await api.getEscalationDetail(item.session_id);
        detailSlot.replaceChildren(renderEscalationDetail(detail));
      } catch (error) {
        showResult(UtilService.errorMessage(error, "Erro ao carregar detalhe."), false);
      } finally {
        detailButton.disabled = false;
      }
    })();
  });

  const briefBlock = reviewBriefBlock(item.review_brief);

  return el("div", { class: "rounded-lg border border-rose-100 bg-white p-4 shadow-sm" }, [
    el("div", { class: "flex items-center justify-between" }, [
      el("p", { class: "font-mono text-sm text-stone-900" }, [text(item.session_id)]),
      detailButton,
    ]),
    ...(briefBlock ? [briefBlock] : []),
    el("p", { class: "mt-1 text-sm text-stone-600" }, [
      text(
        `risco: ${riskDisplayLabel(item.risk_level, item.risk_assessed)} · confiança: ${item.confidence ?? "—"} (threshold: ${item.threshold ?? "—"})`,
      ),
    ]),
    el("p", { class: "mt-1 text-xs text-stone-400" }, [
      text(`escalado em ${formatTimestamp(item.escalated_at)}`),
    ]),
    detailSlot,
    contextInput,
    el("div", { class: "mt-3 flex gap-2" }, [approveButton, rejectButton, reanalyzeButton]),
    resultBox,
  ]);
}

async function refreshApprovals(): Promise<void> {
  const container = UtilService.byId<HTMLDivElement>("approvals-list");
  if (!container) return;
  UtilService.loading(container);

  try {
    const items = await api.listPendingApprovals();
    clear(container);
    if (items.length === 0) {
      container.append(
        el("p", { class: "text-sm text-stone-400" }, [text("Nenhuma aprovação pendente.")]),
      );
      return;
    }
    container.append(...items.map(pendingApprovalCard));
  } catch (error) {
    clear(container);
    MessageBox.show(UtilService.errorMessage(error, "Erro ao carregar aprovações."), "error");
  }
}

function auditRow(entry: AuditEntry): HTMLTableRowElement {
  const cell = (value: string): HTMLTableCellElement =>
    el("td", { class: "border-t border-rose-100 px-3 py-2" }, [text(value)]);
  return el("tr", {}, [
    cell(formatTimestamp(entry.timestamp)),
    cell(translateDecision(entry.decision)),
    cell(entry.actor),
    cell(translateRiskLevel(entry.risk_level)),
    cell(entry.confidence !== null ? String(entry.confidence) : "—"),
    cell(entry.reason ?? entry.tool_authorized ?? "—"),
  ]);
}

async function handleLoadAudit(): Promise<void> {
  MessageBox.hide();
  const input = UtilService.byId<HTMLInputElement>("audit-session-id");
  const container = UtilService.byId<HTMLDivElement>("audit-result");
  if (!input || !container) return;

  const sessionId = input.value.trim();
  if (!sessionId) return;

  clear(container);
  try {
    const entries = await api.getAuditTrail(sessionId);
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
  } catch (error) {
    if (UtilService.isNotFound(error)) {
      container.append(
        el("p", { class: "text-sm text-stone-400" }, [
          text("Nenhuma auditoria encontrada para essa sessão."),
        ]),
      );
    } else {
      MessageBox.show(UtilService.errorMessage(error, "Erro ao carregar auditoria."), "error");
    }
  }
}

function init(): void {
  UtilService.byId<HTMLFormElement>("analyze-form")?.addEventListener(
    "submit",
    (event) => void handleAnalyzeSubmit(event as SubmitEvent),
  );
  UtilService.byId<HTMLButtonElement>("refresh-approvals")?.addEventListener(
    "click",
    () => void refreshApprovals(),
  );
  UtilService.byId<HTMLButtonElement>("load-audit")?.addEventListener(
    "click",
    () => void handleLoadAudit(),
  );
}

document.addEventListener("DOMContentLoaded", init);
