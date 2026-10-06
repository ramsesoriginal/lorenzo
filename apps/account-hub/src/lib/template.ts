// Finding the parts of a component's markup, and copies of its <template>s. Every component
// is an .astro file of data-* hooks and templates plus a renderer that looks them up.

// A lookup that says whose markup is missing a hook: `const required = requiredIn('Briefing')`.
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

// The one element a <template> holds, for a template that is exactly one row, card or box. It is
// taken by being the first element, not by its tag, so its markup can be an <li> today and an
// <article> tomorrow without anything breaking.
export function rootElement(fragment: ParentNode): HTMLElement {
  const root = fragment.firstElementChild;

  if (!(root instanceof HTMLElement)) {
    throw new Error('A template holds no element.');
  }

  return root;
}
