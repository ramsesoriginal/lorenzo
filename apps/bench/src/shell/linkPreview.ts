// What an entry link in LorenzoScript text shows when pointed at (W-C): a small card with the
// entry's name, what it is and the start of its description. It follows the mouse and the keyboard,
// so a link reached with Tab shows it too, and it never takes the focus.

import { parse, render } from '@lorenzo/lorenzoscript';
import { entryIdOfHref } from '../core/links';

/** What the card shows. */
export interface Card {
  name: string;
  what: string;
  excerpt: string;
}

const EXCERPT_CHARS = 180;

/** The start of a description as plain text, cut at a word, for the card. */
export function excerptOf(text: string): string {
  const html = render(parse(text), {});
  const box = document.createElement('div');
  box.innerHTML = html; // escaped by the renderer (ADR 0100); read only for its text
  const plain = (box.textContent ?? '').replace(/\s+/g, ' ').trim();
  if (plain.length <= EXCERPT_CHARS) return plain;
  const cut = plain.slice(0, EXCERPT_CHARS);
  return `${cut.slice(0, cut.lastIndexOf(' ') > 40 ? cut.lastIndexOf(' ') : EXCERPT_CHARS)}…`;
}

/**
 * Shows a card when an entry link inside `root` is hovered or focused. `load` answers with the
 * card for an entry id, or null when there is none to show. The card goes away when the pointer or
 * the focus leaves, and on Escape.
 */
// One card for the whole page: the editors are drawn again whenever something changes, and a card
// that belonged to a drawn-over link would otherwise be left behind.
let card: HTMLElement | null = null;
let turn = 0;

export function hideCard() {
  turn++;
  card?.remove();
  card = null;
}

export function attachLinkPreviews(
  root: HTMLElement,
  load: (id: string) => Promise<Card | null>,
): void {
  const show = async (link: HTMLAnchorElement) => {
    const id = entryIdOfHref(link.getAttribute('href'));
    if (!id) return;
    const at = link.getBoundingClientRect();
    const mine = ++turn;
    const got = await load(id);
    if (mine !== turn || !got) return;
    card?.remove();
    card = document.createElement('div');
    card.className = 'link-card';
    card.setAttribute('role', 'tooltip');
    const name = document.createElement('strong');
    name.textContent = got.name;
    const what = document.createElement('span');
    what.className = 'muted';
    what.textContent = got.what;
    card.append(name, what);
    if (got.excerpt) {
      const p = document.createElement('p');
      p.textContent = got.excerpt;
      card.append(p);
    }
    document.body.append(card);
    card.style.left = `${Math.max(8, Math.min(at.left, window.innerWidth - 328))}px`;
    card.style.top = `${at.bottom + 4}px`;
  };

  const linkOf = (e: Event) =>
    e.target instanceof Element ? e.target.closest<HTMLAnchorElement>('a.ls-entity') : null;

  root.addEventListener('mouseover', (e) => {
    const link = linkOf(e);
    if (link) void show(link);
  });
  root.addEventListener('mouseout', (e) => {
    if (linkOf(e)) hideCard();
  });
  root.addEventListener('focusin', (e) => {
    const link = linkOf(e);
    if (link) void show(link);
  });
  root.addEventListener('focusout', (e) => {
    if (linkOf(e)) hideCard();
  });
  root.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && card) {
      e.stopPropagation();
      hideCard();
    }
  });
}
