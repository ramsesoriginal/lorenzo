import { fromTemplate, requiredIn } from '../../lib/template';

const required = requiredIn('Tenant');

// Puts `node` in the slot `selector` finds in `container`, replacing what was there, or leaves
// the slot empty and hidden when there is nothing for it.
export function fillSlot(container: ParentNode, selector: string, node: Node | null): void {
  const slot = required<HTMLElement>(container, selector);

  slot.replaceChildren(...(node ? [node] : []));
  slot.hidden = node === null;
}

// A fresh copy of a component from its <template>, for its renderer to bind. A component is one
// root element.
export function cloneComponent(container: ParentNode, selector: string): HTMLElement {
  const root = fromTemplate(container, selector).firstElementChild;

  if (!(root instanceof HTMLElement)) {
    throw new Error(`Tenant's ${selector} holds no component.`);
  }

  return root;
}
