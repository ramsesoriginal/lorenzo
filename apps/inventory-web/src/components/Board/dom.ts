export function required<T extends Element>(root: ParentNode, selector: string): T {
  const element = root.querySelector<T>(selector);

  if (!element) {
    throw new Error(`Board is missing ${selector}.`);
  }

  return element;
}

// A fresh copy of one of the board's <template>s.
export function fromTemplate(root: ParentNode, selector: string): DocumentFragment {
  return required<HTMLTemplateElement>(root, selector).content.cloneNode(true) as DocumentFragment;
}
