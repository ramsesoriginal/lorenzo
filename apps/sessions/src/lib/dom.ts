import { BRANDING_CSS_URL } from './config';

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

const SVG = 'http://www.w3.org/2000/svg';
/** An atlas icon (apps/brand/icons.svg). It is decoration: the words beside it carry the meaning. */
export function icon(name: string, className = 'icon') {
  const svg = document.createElementNS(SVG, 'svg');
  svg.setAttribute('class', className);
  svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS(SVG, 'use');
  use.setAttribute('href', `${BRANDING_CSS_URL}/icons.svg#icon-${name}`);
  svg.append(use);
  return svg;
}

/** A field: a label around its control, so the label's words are the control's name. */
export function field(name: string, value = '', type = 'text') {
  const checkbox = type === 'checkbox';
  const label = el('label', '', checkbox ? 'check' : 'field');
  const input = el('input', '', checkbox ? '' : 'text-input');
  input.type = type;
  input.value = value;
  label.append(
    ...(checkbox ? [input, el('span', name)] : [el('span', name, 'field-label'), input]),
  );
  return { label, input };
}
export function select(name: string, options: [string, string][], value = '') {
  const label = el('label', '', 'field');
  const input = el('select', '', 'text-input');
  for (const [id, title] of options) {
    const option = el('option', title);
    option.value = id;
    input.append(option);
  }
  input.value = options.some(([id]) => id === value) ? value : (options[0]?.[0] ?? '');
  label.append(el('span', name, 'field-label'), input);
  return { label, input };
}

type Variant = 'primary' | 'secondary' | 'danger';
/**
 * A button that runs `action` once at a time. A failure is written under the button as an alert
 * and cleared the next time the button is pressed.
 */
export function button(
  name: string,
  action: () => void | Promise<void>,
  options: { variant?: Variant; icon?: string } = {},
) {
  const node = el('button', '', `btn btn-${options.variant ?? 'secondary'}`);
  node.type = 'button';
  if (options.icon) node.append(icon(options.icon));
  node.append(document.createTextNode(name));
  let failure: HTMLElement | undefined;
  node.addEventListener('click', () => {
    failure?.remove();
    failure = undefined;
    node.disabled = true;
    Promise.resolve()
      .then(action)
      .catch((error) => {
        failure = el('p', message(error), 'error-text');
        failure.setAttribute('role', 'alert');
        node.after(failure);
      })
      .finally(() => {
        node.disabled = false;
      });
  });
  return node;
}
/** A submit button; the form's own handler does the work. */
export function submit(name: string, variant: Variant = 'primary') {
  const node = el('button', name, `btn btn-${variant}`);
  node.type = 'submit';
  return node;
}
export function link(name: string, href: string) {
  const node = el('a', name);
  node.href = href;
  return node;
}
/** A link to the page above this one. */
export function backLink(name: string, href: string) {
  const node = el('a', '', 'row-tight');
  node.href = href;
  node.append(icon('previous'), document.createTextNode(name));
  return node;
}
export function sessionHref(tenant: string, id: string, slug?: string | null) {
  return `/session/?${new URLSearchParams({ tenant, ...(slug ? { slug } : { id }) })}`;
}

/** The buttons of one form or row, side by side. */
export function actions(...nodes: HTMLElement[]) {
  const row = el('div', '', 'row');
  row.append(...nodes);
  return row;
}

/** A status line that is read aloud when its text changes, and empty until it has something to say. */
export function statusLine() {
  const node = el('p', '', 'status-text');
  node.setAttribute('role', 'status');
  return node;
}
/** Say something on a status line; an error is announced at once and drawn as one. */
export function say(node: HTMLElement, text: string, failed = false) {
  node.textContent = text;
  node.classList.toggle('error-text', failed);
  node.setAttribute('role', failed ? 'alert' : 'status');
}
/** An error in the page itself, for what could not be opened at all. */
export function errorNotice(error: unknown) {
  const node = el('p', message(error), 'error-text');
  node.setAttribute('role', 'alert');
  return node;
}

/** Something is being fetched: a spinner and words, then blocks where the content will be. */
export function loading(text: string) {
  const host = el('div', '', 'stack');
  host.dataset.loading = '';
  const line = el('p', '', 'status-text row-tight');
  line.setAttribute('role', 'status');
  const spinner = el('span', '', 'spinner');
  spinner.setAttribute('aria-hidden', 'true');
  line.append(spinner, el('span', text));
  host.append(
    line,
    el('div', '', 'skeleton skeleton-block'),
    el('div', '', 'skeleton skeleton-block'),
  );
  return host;
}

/** What a section says when it has nothing to list. */
export const empty = (text: string) => el('p', text, 'status-text');

/** A section's heading with its rule, an optional count and the section's own actions at the right. */
export function sectionHead(
  title: string,
  options: { count?: number; actions?: HTMLElement[] } = {},
) {
  const head = el('div', '', 'section-head');
  head.append(el('h2', title, 'grow'));
  if (options.count !== undefined) head.append(el('span', String(options.count), 'chip'));
  if (options.actions?.length) head.append(actions(...options.actions));
  return head;
}

/** A heading for a group inside a card or a section (levels follow where it sits). */
export const groupTitle = (level: 'h3' | 'h4', text: string) => el(level, text, 'group-title');

/**
 * A closed panel for an editor or a longer list: one summary row with a chevron, and the body
 * underneath. `hint` is a few words about what is inside.
 */
export function panel(title: string, hint = '') {
  const root = el('details', '', 'card panel');
  const summary = el('summary', '', 'panel-summary');
  summary.append(icon('next', 'icon panel-chevron'), el('span', title, 'panel-title'));
  if (hint) summary.append(el('span', hint, 'status-text'));
  const body = el('div', '', 'card-body stack');
  root.append(summary, body);
  return { root, body };
}

/** A card holding one stack of content. */
export function card(...nodes: Node[]) {
  const root = el('div', '', 'card');
  const body = el('div', '', 'card-body stack');
  body.append(...nodes);
  root.append(body);
  return { root, body };
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

/** The neutral label for who can read something: an icon and words, never a colour. */
export function audienceBadge(text: string, shared: boolean) {
  const badge = el('span', '', 'badge-visibility');
  badge.append(icon(shared ? 'social' : 'private'), document.createTextNode(text));
  return badge;
}

/** A link that looks and sits like a button. */
export function linkButton(name: string, href: string) {
  const node = el('a', name, 'btn btn-secondary');
  node.href = href;
  return node;
}

/**
 * The top of a page: the way back, the title (the one serif on the page), a line saying where it
 * is, what is worth knowing at a glance, and the page's own actions at the right.
 */
export function pageHead(
  title: string,
  parts: { crumbs?: HTMLElement[]; lede?: string; meta?: Node[]; actions?: HTMLElement[] } = {},
) {
  const head = el('header', '', 'page-head');
  if (parts.crumbs?.length) {
    const crumbs = el('div', '', 'row crumbs');
    crumbs.append(...parts.crumbs);
    head.append(crumbs);
  }
  const titleRow = el('div', '', 'row');
  titleRow.append(el('h1', title, 'grow'));
  if (parts.actions?.length) titleRow.append(actions(...parts.actions));
  head.append(titleRow);
  if (parts.lede) head.append(el('p', parts.lede, 'lede'));
  if (parts.meta?.length) {
    const meta = el('div', '', 'row');
    meta.append(...parts.meta);
    head.append(meta);
  }
  return head;
}

/** A line of small text with an atlas icon in front, for a fact about the page. */
export function metaLine(iconName: string, text: string) {
  const line = el('span', '', 'row-tight status-text');
  line.append(icon(iconName), document.createTextNode(text));
  return line;
}
