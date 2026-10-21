export function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  text = '',
  className = '',
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  node.textContent = text;
  node.className = className;
  return node;
}
export const message = (error: unknown) =>
  error instanceof Error ? error.message : 'Could not finish this action.';
export function field(name: string, value = '', type = 'text') {
  const label = el('label', name);
  const input = el('input');
  input.type = type;
  input.value = value;
  label.append(input);
  return { label, input };
}
export function select(name: string, options: [string, string][], value = '') {
  const label = el('label', name);
  const input = el('select');
  for (const [id, title] of options) {
    const option = el('option', title);
    option.value = id;
    input.append(option);
  }
  input.value = options.some(([id]) => id === value) ? value : (options[0]?.[0] ?? '');
  label.append(input);
  return { label, input };
}
export function button(name: string, action: () => void | Promise<void>) {
  const node = el('button', name, 'btn btn-secondary');
  node.type = 'button';
  node.addEventListener('click', () => {
    node.disabled = true;
    Promise.resolve()
      .then(action)
      .catch((error) => {
        const status = el('p', message(error));
        status.setAttribute('role', 'alert');
        node.after(status);
      })
      .finally(() => {
        node.disabled = false;
      });
  });
  return node;
}
export function link(name: string, href: string) {
  const node = el('a', name);
  node.href = href;
  return node;
}
export function sessionHref(tenant: string, id: string, slug?: string | null) {
  return `/session/?${new URLSearchParams({ tenant, ...(slug ? { slug } : { id }) })}`;
}

/** Keep a saved view readable while preventing edits against its superseded revision. */
export function suspendControls(root: HTMLElement) {
  const controls = [
    ...root.querySelectorAll<
      HTMLInputElement | HTMLButtonElement | HTMLSelectElement | HTMLTextAreaElement
    >('button, input, select, textarea'),
  ].map((node) => ({ node, disabled: node.disabled }));
  root.setAttribute('aria-busy', 'true');
  for (const { node } of controls) node.disabled = true;
  return () => {
    for (const { node, disabled } of controls) if (node.isConnected) node.disabled = disabled;
    root.removeAttribute('aria-busy');
  };
}
