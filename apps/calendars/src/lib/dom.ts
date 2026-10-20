import { namedParams, tenantAddress } from './addresses';
import { prefetchCalendar, prefetchEntry } from './prefetch';
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
const destinations = new Map<string, { tenant: string; id: string; calendar: boolean }>();
export function entryHref(tenant: string, id: string): string {
  const href = `/entry/?${namedParams(tenant, id)}`;
  destinations.set(href, { tenant, id, calendar: false });
  if (destinations.size > 256) destinations.delete(destinations.keys().next().value ?? '');
  return href;
}
export function calendarHref(tenant: string, id: string, year?: number): string {
  const params = namedParams(tenant, id);
  if (year !== undefined) params.set('year', String(year));
  const href = `/calendar/?${params}`;
  destinations.set(href, { tenant, id, calendar: true });
  if (destinations.size > 256) destinations.delete(destinations.keys().next().value ?? '');
  return href;
}
export function link(text: string, href: string) {
  const a = el('a', text);
  const url = new URL(href, location.origin);
  const tenant = url.searchParams.get('tenant');
  if (url.origin === location.origin && tenant)
    url.searchParams.set('tenant', tenantAddress(tenant));
  a.href = url.href;
  const destination = destinations.get(href);
  if (destination) {
    const read = () =>
      destination.calendar
        ? prefetchCalendar(destination.tenant, destination.id)
        : prefetchEntry(destination.tenant, destination.id);
    a.addEventListener('pointerenter', read);
    a.addEventListener('focus', read);
  }
  return a;
}

if (typeof document !== 'undefined')
  document.addEventListener('astro:before-swap', () => destinations.clear());
