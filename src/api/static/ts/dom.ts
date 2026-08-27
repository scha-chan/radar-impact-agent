/**
 * Helper mínimo de criação de DOM. Existe por um motivo de segurança, não
 * só de estilo: `audit_reason`/`adversarial_reason` podem conter trechos
 * do texto que o próprio usuário submeteu (o detector adversarial, card
 * 18, ecoa o trecho ofensor de volta). Construir elementos via
 * `textContent` em vez de interpolar string em `innerHTML` evita que esse
 * texto seja interpretado como HTML/JS — a mesma classe de risco de um
 * campo de comentário que renderiza sem escapar.
 */

type Attrs = Record<string, string>;

export function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  attrs: Attrs = {},
  children: Array<Node | string> = [],
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else node.setAttribute(key, value);
  }
  for (const child of children) {
    node.append(child instanceof Node ? child : document.createTextNode(child));
  }
  return node;
}

export function clear(node: Element): void {
  node.replaceChildren();
}

export function text(value: string): Text {
  return document.createTextNode(value);
}
