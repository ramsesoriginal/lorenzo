import { namedParams, tenantAddress } from './addresses';
import { BRANDING_CSS_URL } from './config';
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

/** A symbol from the brand's atlas (ADR 0274), decorative: the words beside it say what it means. */
export function icon(name: string, className = ''): SVGSVGElement {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', className ? `icon ${className}` : 'icon');
  svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', `${BRANDING_CSS_URL}/icons.svg#icon-${name}`);
  svg.append(use);
  return svg;
}

/** A button: secondary unless it is the one thing to do here. */
export function button(
  text: string,
  action: () => void | Promise<void>,
  secondary = false,
  symbol?: string,
): HTMLButtonElement {
  const b = el('button', '', secondary ? 'btn btn-secondary' : 'btn btn-primary');
  b.type = 'button';
  if (symbol) b.append(icon(symbol));
  b.append(document.createTextNode(text));
  b.addEventListener('click', () => {
    void action();
  });
  return b;
}

/** A submit button, primary. */
export function submit(text: string): HTMLButtonElement {
  const b = el('button', text, 'btn btn-primary');
  b.type = 'submit';
  return b;
}

let fieldCount = 0;

/**
 * A control with its visible label, joined by `for` and not by wrapping, so the control's own
 * words (a select's options) do not become part of its name.
 */
function labelled<T extends HTMLElement>(
  text: string,
  control: T,
): { label: HTMLElement; input: T } {
  const label = el('div', '', 'field');
  control.id = `calendar-field-${++fieldCount}`;
  const caption = el('label', text, 'field-label');
  caption.htmlFor = control.id;
  label.append(caption, control);
  return { label, input: control };
}

/** A labelled single-line control; the label is the visible name. */
export function field(text: string, value = '', type = 'text') {
  const input = el('input', '', 'text-input');
  input.type = type;
  input.value = value;
  return labelled(text, input);
}

export function textarea(text: string, value = '') {
  const input = el('textarea', '', 'text-input');
  input.value = value;
  return labelled(text, input);
}

export function check(text: string, checked = false) {
  const label = el('label', '', 'field-row');
  const input = el('input');
  input.type = 'checkbox';
  input.checked = checked;
  label.append(input, document.createTextNode(text));
  return { label, input };
}

export function select(text: string, options: [string, string][], value: string) {
  const input = el('select', '', 'text-input');
  for (const [key, name] of options) {
    const o = el('option', name);
    o.value = key;
    input.append(o);
  }
  input.value = value;
  return labelled(text, input);
}

/**
 * A folding section. Plain, with a hairline above, it sits inside a panel; with `boxed` it is a
 * card of its own, for the top of a page. The summary's words are the section's name.
 */
export function disclosure(
  title: string,
  boxed = false,
): { root: HTMLDetailsElement; body: HTMLElement } {
  const root = el('details', '', boxed ? 'card disclosure' : 'disclosure');
  const summary = el('summary');
  summary.append(icon('next', 'disclosure-icon'), document.createTextNode(title));
  const body = el('div', '', 'disclosure-body stack');
  root.append(summary, body);
  return { root, body };
}

/**
 * Where a form or panel says what happened. Empty it takes no room; a message is added when there
 * is one: progress and results politely, a failure as an alert so it is read out.
 */
export function feedback() {
  const node = el('div', '', 'feedback');
  let status: HTMLElement | undefined;
  let error: HTMLElement | undefined;
  const drop = () => {
    status?.remove();
    error?.remove();
    status = undefined;
    error = undefined;
  };
  const writeStatus = () => {
    error?.remove();
    error = undefined;
    if (!status) {
      status = el('p', '', 'status-text');
      status.setAttribute('role', 'status');
      node.append(status);
    }
    return status;
  };
  return {
    node,
    say(text: string) {
      if (!text) return drop();
      const p = writeStatus();
      p.className = 'status-text';
      p.textContent = text;
    },
    /** Something is under way: a spinner, and the words. */
    busy(text: string) {
      const p = writeStatus();
      p.className = 'status-text row-tight';
      const spinner = el('span', '', 'spinner');
      spinner.setAttribute('aria-hidden', 'true');
      p.replaceChildren(spinner, el('span', text));
    },
    fail(text: string) {
      status?.remove();
      status = undefined;
      if (!error) {
        error = el('p', '', 'error-text');
        error.setAttribute('role', 'alert');
        node.append(error);
      }
      error.textContent = text;
    },
    clear: drop,
  };
}

/** A page-level wait: a spinner and what it waits for, until it is removed. */
export function loading(text: string): HTMLElement {
  const p = el('p', '', 'status-text row-tight');
  p.setAttribute('role', 'status');
  const spinner = el('span', '', 'spinner');
  spinner.setAttribute('aria-hidden', 'true');
  p.append(spinner, el('span', text));
  return p;
}

/** A page-level failure, read out as it appears. */
export function failure(text: string): HTMLElement {
  const p = el('p', text, 'error-text');
  p.setAttribute('role', 'alert');
  return p;
}

/** Nothing here yet: what is missing, and what to do about it. */
export function emptyState(title: string, text: string): HTMLElement {
  const box = el('div', '', 'card card-body stack-tight empty-state');
  box.append(el('p', title, 'display empty-title'), el('p', text, 'lede'));
  return box;
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

/** A link with a symbol before its words, such as the way back. */
export function iconLink(text: string, href: string, symbol: string) {
  const a = link(text, href);
  a.prepend(icon(symbol));
  a.classList.add('row-tight');
  return a;
}

/** A link that is an action in its own right, drawn as a quiet button. */
export function linkButton(text: string, href: string, symbol?: string) {
  const a = link(text, href);
  if (symbol) a.prepend(icon(symbol));
  a.className = 'btn btn-secondary';
  return a;
}

if (typeof document !== 'undefined')
  document.addEventListener('astro:before-swap', () => destinations.clear());
