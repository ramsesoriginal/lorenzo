// Menus (ADR 0415): a popover with shortcut hints and a divider before a destructive item; on a phone
// a bottom sheet with tall rows. Arrow keys, Home and End move, Enter or a click chooses, Escape or a
// click outside closes, and focus goes back to what opened it.

import { closeDialog, fadeOnDismiss, openDialog } from './dialog';

export type MenuItem =
  | {
      label: string;
      icon?: string;
      keys?: string;
      /** A count at the right, "3" for unread notifications. */
      badge?: string;
      danger?: boolean;
      /** A radio-style choice: shown as checked or not. */
      checked?: boolean;
      /** A link, or an action. */
      href?: string;
      run?(): void;
    }
  | { separator: true }
  | { heading: string };

export type MenuOptions = {
  label: string;
  sprite: string;
  /** Who is signed in, above the items: a line, or a name over an address. */
  head?: string | { title: string; text?: string };
  /** Whether to be a bottom sheet; the window's phone width unless said otherwise. */
  sheet?: boolean;
};

export type Rect = { left: number; right: number; top: number; bottom: number };

/**
 * Where a popover goes: under its anchor, on the anchor's left edge, or on its right edge when it
 * would run off the window, and above the anchor when there is no room below. Always inside the window.
 */
export function placeMenu(
  anchor: Rect,
  size: { width: number; height: number },
  view: { width: number; height: number },
  gap = 6,
  margin = 8,
): { left: number; top: number } {
  let left = anchor.left;

  if (left + size.width > view.width - margin) left = anchor.right - size.width;
  left = Math.max(margin, Math.min(left, view.width - margin - size.width));

  let top = anchor.bottom + gap;

  if (top + size.height > view.height - margin) top = anchor.top - gap - size.height;
  top = Math.max(margin, top);

  return { left, top };
}

const SVG = 'http://www.w3.org/2000/svg';

function icon(sprite: string, name: string): SVGSVGElement {
  const svg = document.createElementNS(SVG, 'svg');
  const use = document.createElementNS(SVG, 'use');

  svg.setAttribute('class', 'icon');
  svg.setAttribute('aria-hidden', 'true');
  use.setAttribute('href', `${sprite}#icon-${name}`);
  svg.append(use);

  return svg;
}

export function openMenu(
  anchor: HTMLElement,
  items: MenuItem[],
  options: MenuOptions,
): { close(): void } {
  const sheet = options.sheet ?? window.matchMedia?.('(max-width: 720px)').matches ?? false;
  const root = sheet ? document.createElement('dialog') : document.createElement('div');
  const dialog = sheet ? (root as HTMLDialogElement) : null;
  const entries: HTMLElement[] = [];

  root.className = `menu${sheet ? ' as-sheet' : ''}`;
  root.setAttribute('aria-label', options.label);
  if (!sheet) root.setAttribute('role', 'menu');

  if (sheet) {
    const grip = document.createElement('div');

    grip.className = 'sheet-grip';
    grip.setAttribute('aria-hidden', 'true');
    root.append(grip);
  }
  if (options.head) {
    const head = document.createElement('div');

    head.className = 'menu-head';
    if (typeof options.head === 'string') head.textContent = options.head;
    else {
      const title = document.createElement('div');

      title.className = 'menu-head-title';
      title.textContent = options.head.title;
      head.append(title);

      if (options.head.text) {
        const text = document.createElement('div');

        text.className = 'menu-head-text';
        text.textContent = options.head.text;
        head.append(text);
      }
    }
    root.append(head);
  }

  for (const item of items) {
    if ('separator' in item) {
      const rule = document.createElement('div');

      rule.className = 'menu-sep';
      rule.setAttribute('role', 'separator');
      root.append(rule);
      continue;
    }
    if ('heading' in item) {
      const heading = document.createElement('div');

      heading.className = 'menu-label';
      heading.textContent = item.heading;
      root.append(heading);
      continue;
    }

    const entry = item.href ? document.createElement('a') : document.createElement('button');

    entry.className = `menu-item${item.danger ? ' danger' : ''}`;
    entry.setAttribute('role', item.checked === undefined ? 'menuitem' : 'menuitemradio');
    if (item.checked !== undefined) entry.setAttribute('aria-checked', String(item.checked));
    if ('href' in entry) entry.href = item.href ?? '';
    else entry.type = 'button';
    if (item.icon) entry.append(icon(options.sprite, item.icon));

    const label = document.createElement('span');

    label.className = 'grow';
    label.textContent = item.label;
    entry.append(label);
    if (item.badge) {
      const badge = document.createElement('span');

      badge.className = 'menu-badge';
      badge.textContent = item.badge;
      entry.append(badge);
    }
    if (item.keys) {
      const keys = document.createElement('kbd');

      keys.textContent = item.keys;
      entry.append(keys);
    }
    entry.addEventListener('click', () => {
      close();
      if (item.run) setTimeout(item.run, 0);
    });
    entries.push(entry);
    root.append(entry);
  }

  let closed = false;

  function close() {
    if (closed) return;
    closed = true;
    document.removeEventListener('pointerdown', outside, true);
    anchor.setAttribute('aria-expanded', 'false');
    if (dialog) {
      closeDialog(dialog);
      setTimeout(() => root.remove(), 600);
    } else root.remove();
    anchor.focus({ preventScroll: true });
  }

  function outside(event: Event) {
    if (!root.contains(event.target as Node) && event.target !== anchor) close();
  }

  root.addEventListener('keydown', (event) => {
    const keyEvent = event as KeyboardEvent;
    const at = entries.indexOf(document.activeElement as HTMLElement);

    if (keyEvent.key === 'ArrowDown') entries[(at + 1) % entries.length]?.focus();
    else if (keyEvent.key === 'ArrowUp')
      entries[(at - 1 + entries.length) % entries.length]?.focus();
    else if (keyEvent.key === 'Home') entries[0]?.focus();
    else if (keyEvent.key === 'End') entries[entries.length - 1]?.focus();
    else if (keyEvent.key === 'Escape') close();
    else if (keyEvent.key === 'Tab') close();
    else return;

    keyEvent.preventDefault();
  });

  anchor.setAttribute('aria-expanded', 'true');
  document.body.append(root);

  if (dialog) {
    fadeOnDismiss(dialog);
    dialog.addEventListener('close', () => {
      if (!closed) {
        closed = true;
        anchor.setAttribute('aria-expanded', 'false');
      }
    });
    openDialog(dialog);
  } else {
    const rect = anchor.getBoundingClientRect();
    const box = root.getBoundingClientRect();
    const at = placeMenu(
      rect,
      { width: box.width, height: box.height },
      { width: window.innerWidth, height: window.innerHeight },
    );

    root.style.position = 'fixed';
    root.style.left = `${at.left}px`;
    root.style.top = `${at.top}px`;
    root.style.zIndex = '40';
    document.addEventListener('pointerdown', outside, true);
  }
  entries[0]?.focus({ preventScroll: true });

  return { close };
}
