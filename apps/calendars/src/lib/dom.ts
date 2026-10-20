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
export function button(
  text: string,
  action: () => void | Promise<void>,
  secondary = false,
): HTMLButtonElement {
  const b = el('button', text, secondary ? 'btn btn-secondary' : 'btn');
  b.type = 'button';
  b.addEventListener('click', () => {
    void action();
  });
  return b;
}
export function field(
  text: string,
  value = '',
  type = 'text',
): { label: HTMLLabelElement; input: HTMLInputElement } {
  const label = el('label', text);
  const input = el('input');
  input.type = type;
  input.value = value;
  label.append(input);
  return { label, input };
}
export function check(text: string, checked = false) {
  const f = field(text, '', 'checkbox');
  f.label.className = 'check';
  f.input.checked = checked;
  return f;
}
export function select(text: string, options: [string, string][], value: string) {
  const label = el('label', text);
  const input = el('select');
  for (const [key, name] of options) {
    const o = el('option', name);
    o.value = key;
    input.append(o);
  }
  input.value = value;
  label.append(input);
  return { label, input };
}
export const message = (e: unknown): string =>
  e instanceof Error ? e.message : 'Could not finish this action.';
export function entryHref(tenant: string, id: string): string {
  return `/entry/?${new URLSearchParams({ tenant, id })}`;
}
export function calendarHref(tenant: string, id: string, year?: number): string {
  return `/calendar/?${new URLSearchParams({ tenant, id, ...(year === undefined ? {} : { year: String(year) }) })}`;
}
export function link(text: string, href: string) {
  const a = el('a', text);
  a.href = href;
  return a;
}
