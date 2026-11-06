// States (ADR 0413): a region that is loading, empty, failed, partly loaded, in conflict or not on
// this device, and a whole page that has nothing to show or cannot be shown, where a mascot stands.
// Each says what happened in plain words, what it means for the work, and offers one next step.
// A hidden thing is never counted: no state says how many entries a person cannot see.

const SVG = 'http://www.w3.org/2000/svg';

export type RegionStateKind =
  | 'empty'
  | 'empty-search'
  | 'loading'
  | 'error'
  | 'partial'
  | 'conflict'
  | 'offline';

export type StateAction = { label: string; run(): void; primary?: boolean };

export type RegionStateSpec = {
  kind: RegionStateKind;
  /** What the region holds, for the words ("entries", "beings"). */
  noun?: string;
  title?: string;
  text?: string;
  /** A short code for support, e.g. "503 · request 4f2a91". */
  code?: string;
  actions?: StateAction[];
  /** For `loading`: it has gone on longer than usual. */
  slow?: boolean;
  /** For `partial`: how many were shown and how many were not. */
  shown?: number;
  missing?: number;
};

const ICON: Record<RegionStateKind, string | null> = {
  empty: 'kind-entity-dashed',
  'empty-search': 'search',
  loading: null,
  error: 'warning',
  partial: 'warning',
  conflict: 'conflict',
  offline: 'offline',
};

function el<K extends keyof HTMLElementTagNameMap>(tag: K, className?: string, text?: string) {
  const node = document.createElement(tag);

  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;

  return node;
}

function icon(sprite: string, name: string): SVGSVGElement {
  const svg = document.createElementNS(SVG, 'svg');
  const use = document.createElementNS(SVG, 'use');

  svg.setAttribute('class', 'icon');
  svg.setAttribute('aria-hidden', 'true');
  use.setAttribute('href', `${sprite}#icon-${name}`);
  svg.append(use);

  return svg;
}

function actionButton(action: StateAction): HTMLButtonElement {
  const button = el(
    'button',
    `btn ${action.primary ? 'btn-primary' : 'btn-secondary'}`,
    action.label,
  );

  button.type = 'button';
  button.addEventListener('click', () => action.run());

  return button;
}

/** The words of a region state, from the design, before the app's own are applied. */
export function regionWords(spec: RegionStateSpec): { title: string; text: string } {
  const noun = spec.noun ?? 'entries';

  switch (spec.kind) {
    case 'empty':
      return {
        title: `No ${noun} yet`,
        text: 'Add a person, place, event, object, or whatever else exists here.',
      };
    case 'empty-search':
      return {
        title: `No ${noun} match`,
        text: 'Try a different word, or clear the filters.',
      };
    case 'loading':
      return {
        title: `Loading ${noun}`,
        text: spec.slow ? 'Still loading. This is taking longer than usual.' : '',
      };
    case 'error':
      return {
        title: `Couldn’t load ${noun}`,
        text: 'The connection dropped before this finished. Nothing you wrote is lost.',
      };
    case 'partial':
      return {
        title: `Some ${noun} didn’t load`,
        text:
          spec.shown !== undefined && spec.missing !== undefined
            ? `Showing ${spec.shown}. ${spec.missing} could not be loaded.`
            : 'Some of them could not be loaded.',
      };
    case 'conflict':
      return {
        title: 'This changed while you were editing',
        text: 'Your version and theirs both exist.',
      };
    case 'offline':
      return {
        title: 'Not on this device yet',
        text: 'Reconnect to open it. What you have already saved here is still available.',
      };
  }
}

/** A state for a region: replaces nothing itself, so the caller puts it where the rows were. */
export function regionState(sprite: string, spec: RegionStateSpec): HTMLElement {
  const words = regionWords(spec);
  const block = el('div', 'state-block');

  block.dataset.kind = spec.kind;

  if (spec.kind === 'loading') {
    block.setAttribute('role', 'status');
    block.setAttribute('aria-label', spec.title ?? words.title);

    for (const width of [70, 90, 55, 80]) {
      const line = el('div', 'skeleton skeleton-line');

      line.style.width = `${width}%`;
      block.append(line);
    }
    if (words.text) block.append(el('p', undefined, spec.text ?? words.text));

    return block;
  }

  const name = ICON[spec.kind];

  if (name) block.append(icon(sprite, name));
  block.append(el('div', 'state-block-title', spec.title ?? words.title));
  block.append(el('p', undefined, spec.text ?? words.text));
  if (spec.code) block.append(el('div', 'state-block-code', spec.code));
  if (spec.actions && spec.actions.length > 0) {
    const actions = el('div', 'state-block-actions');

    actions.append(...spec.actions.map(actionButton));
    block.append(actions);
  }
  // A failure is announced; an empty region is just there.
  if (spec.kind === 'error' || spec.kind === 'conflict') block.setAttribute('role', 'alert');

  return block;
}

/** The images the mascots need (mascot-images.md), by id. Others are allowed: an app names its own. */
export type MascotId =
  | 'first-run-welcome'
  | 'empty-entries'
  | 'empty-notes'
  | 'empty-manuscript'
  | 'empty-map'
  | 'empty-inventory'
  | 'empty-sessions'
  | 'empty-beings'
  | 'empty-calendar'
  | 'empty-social-types'
  | 'empty-relationships'
  | 'empty-social-web'
  | 'device-connected'
  | 'caught-up'
  | 'page-not-found'
  | 'no-access'
  | 'offline-page'
  | 'error-page'
  | 'maintenance';

export type PageStateSpec = {
  /** The image: a MascotId, or the id an app's own design lists. */
  art: MascotId | (string & {});
  /** What the image shows, as alt text; the art itself has no words. */
  alt?: string;
  /** The page's heading; the shared states (no access, not found, …) have their own words. */
  title?: string;
  /** The heading's level: 1 for a page that is only this, 2 when it stands inside a page that has its own heading. */
  level?: 1 | 2;
  text?: string;
  actions?: StateAction[];
  /** An address for a link as the one next step, when going somewhere is the step. */
  link?: { label: string; href: string };
};

/** The words of the page states that every app shares (ADR 0413, identity section 14). */
export const PAGE_WORDS: Partial<Record<MascotId, { title: string; text: string; alt: string }>> = {
  'page-not-found': {
    title: 'Catileo appears to have misplaced this page',
    text: 'It may have moved, or it may never have been here.',
    alt: 'Catileo beside an empty spot where a page should be',
  },
  'no-access': {
    title: 'This page isn’t available',
    text: 'It may not exist, or you may not have access. Ask a GM or an Organizer of the library to share it with you.',
    alt: 'Catileo before a closed door',
  },
  'offline-page': {
    title: 'You’re offline',
    text: 'This app needs a connection to start. What you have saved on this device opens again once it does.',
    alt: 'Lorenzo reading by a lantern, Catileo asleep nearby',
  },
  'error-page': {
    title: 'Something went wrong on our side',
    text: 'Nothing you wrote is lost. Try again in a moment.',
    alt: 'Catileo startled beside a toppled stack of papers',
  },
  'caught-up': {
    title: 'You’re all caught up',
    text: '',
    alt: 'Catileo asleep on a folded blanket',
  },
  'empty-entries': {
    title: 'No entries yet',
    text: 'Add a person, place, event, object, or whatever else exists here.',
    alt: 'Lorenzo holding up a blank index card',
  },
};

/**
 * A state that replaces a whole page, with a mascot. `base` is where the brand serves the images:
 * `${base}/mascots/ui_<id>.png`. An image that is not there yet leaves a placeholder; the words
 * carry the meaning either way.
 */
export function pageState(base: string, spec: PageStateSpec): HTMLElement {
  const known = PAGE_WORDS[spec.art as MascotId];
  const block = el('div', 'page-state');
  const art = el('div', 'page-state-art');
  const alt = spec.alt ?? known?.alt ?? '';
  const image = el('img');
  const text = spec.text ?? known?.text ?? '';

  image.alt = alt;
  image.src = `${base}/mascots/ui_${spec.art}.png`;
  image.addEventListener('error', () => {
    art.dataset.missing = '';
    art.replaceChildren(document.createTextNode(alt));
  });
  art.append(image);
  block.append(
    art,
    el(spec.level === 2 ? 'h2' : 'h1', undefined, spec.title ?? known?.title ?? ''),
  );
  if (text) block.append(el('p', undefined, text));

  if (spec.link) {
    const link = el('a', 'btn btn-secondary', spec.link.label);

    link.href = spec.link.href;
    block.append(link);
  }
  if (spec.actions && spec.actions.length > 0) {
    const actions = el('div', 'state-block-actions');

    actions.append(...spec.actions.map(actionButton));
    block.append(actions);
  }

  return block;
}
