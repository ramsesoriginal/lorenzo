// The card a link to an entity opens when it is hovered, focused or tapped (ADR 0264), for every
// `.ls-content` on the page. One card for the page; listeners on the document, since the texts
// are drawn and drawn again. The timing is previewState.ts's; the words are the API's.

import { blobUrl } from '../../lib/api';
import { type Card, kindLabel, loadCard, previewTarget, statText } from '../../lib/linkPreview';
import { createPreviewState } from '../../lib/previewState';

const CARD_ID = 'link-preview';
const LINKS = '.ls-content a.ls-entity';

const linkOf = (event: Event): HTMLAnchorElement | null =>
  event.target instanceof Element ? event.target.closest<HTMLAnchorElement>(LINKS) : null;

function draw(card: Card): HTMLElement {
  const box = document.createElement('div');
  box.id = CARD_ID;
  box.className = 'link-preview';
  box.setAttribute('role', 'tooltip');
  const text = document.createElement('div');
  text.className = 'link-preview-text';
  const name = document.createElement('strong');
  name.textContent = card.name;
  const what = document.createElement('span');
  what.className = 'link-preview-kind';
  what.textContent = kindLabel(card.kinds);
  text.append(name, what);
  if (card.stats.length) {
    const stats = document.createElement('span');
    stats.className = 'link-preview-stats';
    stats.textContent = card.stats.map(statText).join(' · ');
    text.append(stats);
  }
  if (card.excerpt) {
    const excerpt = document.createElement('p');
    excerpt.textContent = card.excerpt;
    text.append(excerpt);
  }
  box.append(text);
  return box;
}

function place(box: HTMLElement, link: HTMLElement) {
  const at = link.getBoundingClientRect();
  const width = box.offsetWidth;
  const height = box.offsetHeight;
  const left = Math.max(8, Math.min(at.left, window.innerWidth - width - 8));
  const below = at.bottom + 6;
  const top =
    below + height > window.innerHeight && at.top - height - 6 > 0 ? at.top - height - 6 : below;
  box.style.left = `${left}px`;
  box.style.top = `${top}px`;
}

export function installLinkPreviews(): void {
  let box: HTMLElement | null = null;
  let owner: HTMLAnchorElement | null = null;
  // Bumped whenever the card is closed or another opens, so a card that arrives late is dropped.
  let turn = 0;
  let touched = false;

  const state = createPreviewState<HTMLAnchorElement>(
    (link) => void open(link),
    () => close(),
  );

  function close() {
    turn++;
    box?.remove();
    box = null;
    owner?.removeAttribute('aria-describedby');
    owner = null;
  }

  async function open(link: HTMLAnchorElement) {
    close();
    const mine = turn;
    const target = previewTarget(link.getAttribute('href'));
    if (!target) return;
    const card = await loadCard(target.tenant, target.id);
    // Closed, or another link opened, or the text was drawn over, while it loaded.
    if (mine !== turn || !card || !link.isConnected) return;
    box = draw(card);
    box.addEventListener('pointerenter', () => state.holdCard());
    box.addEventListener('pointerleave', () => state.leave());
    document.body.append(box);
    place(box, link);
    link.setAttribute('aria-describedby', CARD_ID);
    owner = link;
    if (card.picture_url) {
      const shown = box;
      void blobUrl(card.picture_url)
        .then((src) => {
          if (box !== shown) return;
          const picture = document.createElement('img');
          picture.className = 'link-preview-picture';
          picture.alt = '';
          picture.src = src;
          shown.prepend(picture);
          place(shown, link);
        })
        .catch(() => {});
    }
  }

  document.addEventListener('pointerdown', (event) => {
    touched = event.pointerType === 'touch';
    // Touching anything but a link or the card puts the card away.
    if (!linkOf(event) && !(event.target instanceof Element && event.target.closest(`#${CARD_ID}`)))
      state.dismiss();
  });
  document.addEventListener('pointerover', (event) => {
    if (event.pointerType === 'touch') return;
    const link = linkOf(event);
    if (link) state.enter(link);
  });
  document.addEventListener('pointerout', (event) => {
    if (event.pointerType === 'touch') return;
    if (linkOf(event)) state.leave();
  });
  document.addEventListener('focusin', (event) => {
    const link = linkOf(event);
    if (link) state.focus(link);
  });
  document.addEventListener('focusout', (event) => {
    if (linkOf(event)) state.blur();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && state.shown()) {
      state.escape();
    }
  });
  document.addEventListener('click', (event) => {
    const link = linkOf(event);
    // The first tap shows the card; the second, on the same link, follows it.
    if (link && touched && previewTarget(link.getAttribute('href')) && !state.tap(link))
      event.preventDefault();
  });
  // A card at the old place of a link that has moved is wrong; the next hover draws it again.
  window.addEventListener('scroll', () => state.dismiss(), { passive: true, capture: true });
}
