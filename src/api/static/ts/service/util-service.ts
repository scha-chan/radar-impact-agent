/**
 * `UtilService` — comandos de tela que se repetem em `app.ts`: pegar um
 * elemento por id, extrair a mensagem amigável de um erro de chamada,
 * marcar um botão como ocupado, mostrar um "carregando" num container.
 * `MessageBox` cuida da faixa de mensagem global (`#message-box`), usada
 * por todas as três telas (análise, aprovações, auditoria).
 *
 * Sem estado próprio — só encapsula padrões que estavam copiados. A
 * construção segura de DOM continua em `dom.ts`; a tradução/formatação de
 * exibição, em `i18n.ts`.
 */

import { clear, el, text } from "../dom.js";
import { ApiError } from "./radar-api-client.js";

export const UtilService = {
  /** `document.querySelector` tipado por `#id`; `null` se não existir. */
  byId<T extends HTMLElement>(id: string): T | null {
    return document.querySelector<T>(`#${id}`);
  },

  /**
   * Mensagem para exibir a partir de um erro de chamada: usa
   * `ApiError.message` (que já traz o `detail` do backend) quando for um,
   * senão o texto de fallback do contexto.
   */
  errorMessage(error: unknown, fallback: string): string {
    return error instanceof ApiError ? error.message : fallback;
  },

  /** `true` se o erro é um 404 da API — recurso inexistente ou já resolvido. */
  isNotFound(error: unknown): boolean {
    return error instanceof ApiError && error.status === 404;
  },

  /**
   * Desabilita `button` e troca o rótulo por "…" enquanto `run` executa;
   * restaura os dois no fim, mesmo se `run` lançar. Devolve o resultado
   * de `run`.
   */
  async busy<T>(button: HTMLButtonElement, run: () => Promise<T>): Promise<T> {
    const label = button.textContent ?? "";
    button.disabled = true;
    button.textContent = "…";
    try {
      return await run();
    } finally {
      button.disabled = false;
      button.textContent = label;
    }
  },

  /** Substitui o conteúdo de `container` por um placeholder de carregando. */
  loading(container: Element, message = "Carregando..."): void {
    clear(container);
    container.append(el("p", { class: "text-sm text-stone-400" }, [text(message)]));
  },
};

/** Faixa de mensagem global (`#message-box`), compartilhada pelas telas. */
export const MessageBox = {
  show(message: string, tone: "error" | "info" = "info"): void {
    const box = document.querySelector<HTMLDivElement>("#message-box");
    if (!box) return;
    const toneClass =
      tone === "error"
        ? "bg-red-50 text-red-800 border border-red-200"
        : "bg-rose-50 text-rose-800 border border-rose-200";
    clear(box);
    box.className = `rounded-lg px-4 py-3 text-sm ${toneClass}`;
    box.append(text(message));
    box.classList.remove("hidden");
  },

  hide(): void {
    document.querySelector<HTMLDivElement>("#message-box")?.classList.add("hidden");
  },
};
