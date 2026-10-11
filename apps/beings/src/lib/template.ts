// Finding the parts of a component's markup, and copies of its <template>s. Every component
// is an .astro file of data-* hooks and templates plus a renderer that looks them up.

// A lookup that says whose markup is missing a hook: `const required = requiredIn('Catalog')`.
export function requiredIn(who: string) {
  return <T extends Element>(root: ParentNode, selector: string): T => {
    const element = root.querySelector<T>(selector);

    if (!element) {
      throw new Error(`${who} is missing ${selector}.`);
    }

    return element;
  };
}

// A fresh copy of one of `root`'s <template>s, for when it has several elements to take from.
export function fromTemplate(root: ParentNode, selector: string): DocumentFragment {
  return requiredIn('Template')<HTMLTemplateElement>(root, selector).content.cloneNode(
    true,
  ) as DocumentFragment;
}

// A fresh copy of the element `selector` finds in `template`, or of its first element.
export function cloneTemplate<T extends Element>(
  template: HTMLTemplateElement,
  selector?: string,
): T {
  const fragment = template.content.cloneNode(true) as DocumentFragment;
  const found = selector ? fragment.querySelector<T>(selector) : fragment.firstElementChild;

  if (!found) {
    throw new Error(`A template has no ${selector ?? 'element'}.`);
  }

  return found as T;
}
