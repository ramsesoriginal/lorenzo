// The card an element opens when it is hovered, focused or tapped (ADR 0264, 0349): one card for
// the page, listeners on the document (the page's contents are drawn and drawn again), the timing
// from state.ts and the words from the API. Nothing is drawn until an element is pointed at.

import { createPreviewState } from './state';
import type { EntryCard, PreviewTarget } from './types';
import { kindLabel, statText } from './words';

export type EntryPreviewOptions = {
  /** Which elements open a card; an element inside one counts as the one. HTML or SVG. */
  selector: string;
  /** The library and entry a matched element stands for, or null when it stands for none. */
  targetOf(element: Element): PreviewTarget | null;
  /** The card for an entry, or null when there is none (the API's preview route, cached). */
  loadCard(tenant: string, id: string): Promise<EntryCard | null>;
  /** How a protected picture's URL becomes something an `<img>` can show. No picture without it. */
  loadPicture?(url: string): Promise<string>;
  /**
   * `"two-taps"`: the first tap on a trigger shows its card and does not follow it, the second
   * does. `"off"`: a tap does what a click does and touch never opens a card.
   */
  touch?: 'two-taps' | 'off';
  /** The card's element id, which `aria-describedby` names while it is open. */
  id?: string;
  document?: Document;
};

export type EntryPreview = {
  /** Removes every listener and the card. */
  destroy(): void;
};

function draw(doc: Document, id: string, card: EntryCard): HTMLElement {
  const box = doc.createElement('div');
  box.id = id;
  box.className = 'entry-preview';
  box.setAttribute('role', 'tooltip');
  const text = doc.createElement('div');
  text.className = 'entry-preview-text';
  const name = doc.createElement('strong');
  name.textContent = card.name;
  const what = doc.createElement('span');
  what.className = 'entry-preview-kind';
  what.textContent = kindLabel(card.kinds);
  text.append(name, what);
  if (card.stats.length) {
    const stats = doc.createElement('span');
    stats.className = 'entry-preview-stats';
    stats.textContent = card.stats.map(statText).join(' · ');
    text.append(stats);
  }
  if (card.excerpt) {
    const excerpt = doc.createElement('p');
    excerpt.textContent = card.excerpt;
    text.append(excerpt);
  }
  box.append(text);
  return box;
}

/** Under the trigger, or above it when there is no room, and inside the window. */
function place(win: Window, box: HTMLElement, trigger: Element) {
  const at = trigger.getBoundingClientRect();
  const width = box.offsetWidth;
  const height = box.offsetHeight;
  const left = Math.max(8, Math.min(at.left, win.innerWidth - width - 8));
  const below = at.bottom + 6;
  const top =
    below + height > win.innerHeight && at.top - height - 6 > 0 ? at.top - height - 6 : below;
  box.style.left = `${left}px`;
  box.style.top = `${top}px`;
}

export function installEntryPreview(options: EntryPreviewOptions): EntryPreview {
  const doc = options.document ?? document;
  const win = doc.defaultView ?? window;
  const id = options.id ?? 'entry-preview';
  const twoTaps = (options.touch ?? 'two-taps') === 'two-taps';
  const control = new AbortController();
  const { signal } = control;

  let box: HTMLElement | null = null;
  let owner: Element | null = null;
  // Bumped whenever the card is closed or another opens, so a card that arrives late is dropped.
  let turn = 0;
  let touched = false;

  const triggerOf = (event: Event): Element | null =>
    event.target instanceof Element ? event.target.closest(options.selector) : null;
  const targetOf = (trigger: Element) => options.targetOf(trigger);

  const state = createPreviewState<Element>(
    (trigger) => void open(trigger),
    () => close(),
  );

  function close() {
    turn++;
    box?.remove();
    box = null;
    owner?.removeAttribute('aria-describedby');
    owner = null;
  }

  async function open(trigger: Element) {
    close();
    const mine = turn;
    const target = targetOf(trigger);
    if (!target) return;
    const card = await options.loadCard(target.tenant, target.id);
    // Closed, or another trigger opened, or the page was drawn over, while it loaded.
    if (mine !== turn || !card || !trigger.isConnected) return;
    const shown = draw(doc, id, card);
    box = shown;
    shown.addEventListener('pointerenter', () => state.holdCard(), { signal });
    shown.addEventListener('pointerleave', () => state.leave(), { signal });
    // Inside the page's main landmark, so the card is not content outside every landmark; it is
    // fixed to the window, so where it sits in the page does not place it.
    (doc.querySelector('main') ?? doc.body).append(shown);
    place(win, shown, trigger);
    trigger.setAttribute('aria-describedby', id);
    owner = trigger;
    const picture = options.loadPicture;
    if (card.picture_url && picture) {
      void picture(card.picture_url)
        .then((src) => {
          if (box !== shown) return;
          const image = doc.createElement('img');
          image.className = 'entry-preview-picture';
          image.alt = '';
          image.src = src;
          shown.prepend(image);
          place(win, shown, trigger);
        })
        .catch(() => {});
    }
  }

  doc.addEventListener(
    'pointerdown',
    (event) => {
      touched = event.pointerType === 'touch';
      // Touching anything but a trigger or the card puts the card away.
      if (!triggerOf(event) && !(event.target instanceof Element && event.target.closest(`#${id}`)))
        state.dismiss();
    },
    { signal },
  );
  doc.addEventListener(
    'pointerover',
    (event) => {
      if (event.pointerType === 'touch') return;
      const trigger = triggerOf(event);
      if (trigger) state.enter(trigger);
    },
    { signal },
  );
  doc.addEventListener(
    'pointerout',
    (event) => {
      if (event.pointerType === 'touch') return;
      if (triggerOf(event)) state.leave();
    },
    { signal },
  );
  doc.addEventListener(
    'focusin',
    (event) => {
      // A tap focuses the trigger too; the tap's own click decides what it does.
      if (touched) return;
      const trigger = triggerOf(event);
      if (trigger) state.focus(trigger);
    },
    { signal },
  );
  doc.addEventListener(
    'focusout',
    (event) => {
      if (triggerOf(event)) state.blur();
    },
    { signal },
  );
  doc.addEventListener(
    'keydown',
    (event) => {
      touched = false;
      if (event.key === 'Escape' && state.shown()) state.escape();
    },
    { signal },
  );
  if (twoTaps) {
    doc.addEventListener(
      'click',
      (event) => {
        const trigger = triggerOf(event);
        // The first tap shows the card; the second, on the same trigger, follows it.
        if (trigger && touched && targetOf(trigger) && !state.tap(trigger)) event.preventDefault();
      },
      { signal },
    );
  }
  // The card follows its trigger when the page scrolls, and is put away when the trigger leaves the
  // window. A card still loading is placed when it arrives, so focusing a trigger that scrolls into
  // view does not cancel its own card.
  win.addEventListener(
    'scroll',
    () => {
      if (!box || !owner) return;
      const at = owner.getBoundingClientRect();
      if (!owner.isConnected || at.bottom < 0 || at.top > win.innerHeight) state.dismiss();
      else place(win, box, owner);
    },
    { passive: true, capture: true, signal },
  );

  return {
    destroy() {
      control.abort();
      close();
    },
  };
}
