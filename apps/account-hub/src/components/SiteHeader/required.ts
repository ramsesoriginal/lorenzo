// Finds a part of the header's markup by its hook, and says which one is missing if it isn't there.
export function required<T extends Element>(root: ParentNode, selector: string): T {
  const element = root.querySelector<T>(selector);

  if (!element) {
    throw new Error(`Site header is missing ${selector}.`);
  }

  return element;
}
