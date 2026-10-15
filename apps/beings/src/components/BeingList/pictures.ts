// List portraits use ADR 0264's visibility-filtered preview, never a guessed file URL.
import { blobUrl, client, unwrap } from '../../lib/api';
import { createBeingPictures } from '../../lib/beingPictures';
import { requiredIn } from '../../lib/template';

const required = requiredIn('Being pictures');

export function renderListPictures(root: HTMLElement, tenantId: string) {
  const box = required<HTMLElement>(root, '[data-picture-preview]');
  const large = required<HTMLImageElement>(box, 'img');
  const desktop = window.matchMedia('(hover: hover) and (pointer: fine)');
  const load = createBeingPictures(async (id) => {
    const card = await unwrap(
      await client.GET('/tenants/{tenant_id}/entities/{entity_id}/preview', {
        params: { path: { tenant_id: tenantId, entity_id: id } },
      }),
    );
    return card.picture_url ? blobUrl(card.picture_url) : null;
  });
  const fills = new WeakMap<Element, () => void>();
  let active: HTMLElement | null = null;
  let x = 0;
  let y = 0;
  let frame = 0;

  function hide() {
    active?.querySelector('a')?.removeAttribute('aria-describedby');
    active = null;
    box.hidden = true;
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
  }

  function place() {
    frame = 0;
    if (box.hidden) return;
    const size = box.offsetWidth;
    const margin = 16;
    const right = x + 24;
    const left = right + size <= window.innerWidth - margin ? right : x - size - 24;
    box.style.left = `${Math.max(margin, Math.min(left, window.innerWidth - size - margin))}px`;
    box.style.top = `${Math.max(margin, Math.min(y - size / 2, window.innerHeight - size - margin))}px`;
  }

  function show(row: HTMLElement, image: HTMLImageElement, name: string) {
    if (active !== row || !row.isConnected || !desktop.matches || image.hidden) return;
    large.src = image.src;
    large.alt = `Picture of ${name}`;
    box.hidden = false;
    row.querySelector('a')?.setAttribute('aria-describedby', box.id);
    place();
  }

  const observer =
    typeof IntersectionObserver === 'undefined'
      ? null
      : new IntersectionObserver(
          (entries) => {
            for (const entry of entries) {
              if (!entry.isIntersecting) continue;
              observer?.unobserve(entry.target);
              fills.get(entry.target)?.();
            }
          },
          { rootMargin: '160px' },
        );

  window.addEventListener('scroll', hide, { capture: true, passive: true });
  window.addEventListener('resize', hide);
  window.addEventListener('pagehide', hide);
  desktop.addEventListener('change', hide);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') hide();
  });

  return {
    reset() {
      hide();
      observer?.disconnect();
    },
    observe(row: HTMLElement, id: string, name: string) {
      const image = required<HTMLImageElement>(row, '[data-list-picture]');
      row.dataset.pictureState = 'loading';
      let loading = false;
      async function fill() {
        if (loading || row.dataset.pictureState === 'ready' || row.dataset.pictureState === 'none')
          return;
        loading = true;
        const src = await load(id);
        loading = false;
        if (!row.isConnected) return;
        if (!src) {
          row.dataset.pictureState = 'none';
          return;
        }
        image.onload = () => {
          image.hidden = false;
          row.dataset.pictureState = 'ready';
          show(row, image, name);
        };
        image.onerror = () => {
          image.hidden = true;
          row.dataset.pictureState = 'none';
          if (active === row) hide();
        };
        image.src = src;
      }
      fills.set(row, () => {
        void fill();
      });
      if (observer) observer.observe(row);
      else
        queueMicrotask(() => {
          void fill();
        });
      row.addEventListener('pointerenter', (event) => {
        if (!desktop.matches || event.pointerType === 'touch') return;
        hide();
        active = row;
        x = event.clientX;
        y = event.clientY;
        void fill();
        show(row, image, name);
      });
      row.addEventListener('pointermove', (event) => {
        if (active !== row) return;
        x = event.clientX;
        y = event.clientY;
        if (!frame) frame = requestAnimationFrame(place);
      });
      row.addEventListener('pointerleave', () => {
        if (active === row) hide();
      });
      row.addEventListener('focusin', () => {
        if (!desktop.matches) return;
        hide();
        active = row;
        const at = row.getBoundingClientRect();
        x = at.right;
        y = at.top + at.height / 2;
        void fill();
        show(row, image, name);
      });
      row.addEventListener('focusout', () => {
        if (active === row) hide();
      });
      row.querySelector('a')?.addEventListener('click', hide);
    },
  };
}
