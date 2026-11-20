// The frame of a being's sheet (RFC 0043, BN2, BN7): the mode, the order of the sections, the band
// that keeps the mode switch, what the mode is for and the pinned numbers in view (it shrinks and
// shows the name once the header has scrolled away), and the one small live region that says what
// changed. It draws no content itself.

import { DEFAULT_GM_WORDS } from '../../lib/gmTitle';
import {
  isLayout,
  isMode,
  type Layout,
  type Mode,
  modeLineFor,
  rememberMode,
  savedMode,
  sectionOrder,
} from '../../lib/sheetMode';
import { requiredIn } from '../../lib/template';

export type SheetControlsOptions = {
  // The page: the header, the sticky bar, the sections and the live region are found in it.
  root: HTMLElement;
  // After the drawn mode changed, so the parts that depend on it can redraw.
  onMode: (mode: Mode) => void;
  // After the layout changed, so the datasheet can be read when it is first wanted.
  onLayout: (layout: Layout) => void;
};

export type RenderedSheetControls = {
  /**
   * Whether the viewer may change this being: its edit controls show in Read. Whoever may also gets
   * the mode they last used on this being, so a player at the table lands in Play (BN5).
   */
  allowEdit(allowed: boolean, tenantId: string, entityId: string): void;
  /** The mode being drawn. */
  mode(): Mode;
  /** The layout being drawn. */
  layout(): Layout;
  /** Says something to screen readers, through the one live region. */
  announce(message: string): void;
  setName(name: string): void;
  /** What the being's campaign calls its game master, for the line of the band (ADR 0294). */
  setGmWord(title: string): void;
  /** Opens or closes the being's details (picture, name, link name, tags); Play goes to Read first. */
  toggleDetails(): void;
  /** What the band's Undo says it would take back, and how many steps there are (null: none). */
  setSteps(count: number, last: string | null): void;
};

const required = requiredIn('Sheet controls');

export function renderSheetControls(options: SheetControlsOptions): RenderedSheetControls {
  const { root } = options;
  const head = required<HTMLElement>(root, '[data-sheet-head]');
  const bar = required<HTMLElement>(root, '[data-sticky]');
  const barName = required<HTMLElement>(bar, '[data-sticky-name]');
  const main = required<HTMLElement>(root, '[data-sheet-main]');
  const live = required<HTMLElement>(root, '[data-live]');
  const switches = [...root.querySelectorAll<HTMLElement>('[data-mode-switch]')];
  const layoutSwitches = [...root.querySelectorAll<HTMLElement>('[data-layout-switch]')];

  const modeLine = required<HTMLElement>(root, '[data-mode-line]');
  const more = required<HTMLButtonElement>(root, '[data-more]');
  const closeDetails = required<HTMLButtonElement>(root, '[data-close-details]');
  const undoLast = required<HTMLElement>(root, '[data-band-last]');
  const historyCount = required<HTMLElement>(root, '[data-band-count]');

  let wanted: Mode = 'read';
  let layout: Layout = 'sheet';
  let canEdit = false;
  let detailsOpen = false;
  let gmWord = DEFAULT_GM_WORDS.title;
  // The person has chosen a mode on this page, so what was remembered no longer decides.
  let chosen = false;
  // Where the mode is remembered, once the being is known.
  let memory: { tenantId: string; entityId: string } | null = null;

  const shown = (): Mode => wanted;

  // One small live region, so a screen reader hears "Play mode" and not the whole page.
  function announce(message: string) {
    live.textContent = '';
    window.setTimeout(() => {
      live.textContent = message;
    }, 30);
  }

  function apply() {
    const mode = shown();

    root.dataset.mode = mode;

    for (const group of switches) {
      for (const radio of group.querySelectorAll<HTMLInputElement>('input')) {
        radio.checked = radio.value === mode;
      }
    }

    modeLine.textContent = modeLineFor(mode, canEdit, gmWord);

    // The order of the sections follows the mode.
    for (const [index, name] of sectionOrder(mode).entries()) {
      const section = main.querySelector<HTMLElement>(`[data-section="${name}"]`);

      if (section) section.style.order = String(index);
    }

    // What changes the being is for Read, and for whoever may change it; Play has none of it.
    const editing = canEdit && mode === 'read';

    if (!editing) detailsOpen = false;
    more.hidden = !canEdit;
    more.setAttribute('aria-expanded', 'false');

    for (const part of root.querySelectorAll<HTMLElement>('[data-only-in]')) {
      part.hidden = !(editing && (part.dataset.onlyIn ?? '') === 'edit');
    }

    // Undo and History are for the table, and for whoever may change the being there.
    for (const part of root.querySelectorAll<HTMLElement>('[data-only-play]')) {
      part.hidden = !(mode === 'play' && canEdit);
    }

    for (const part of root.querySelectorAll<HTMLElement>('[data-details]')) {
      part.hidden = !(editing && detailsOpen);
    }

    options.onMode(mode);
  }

  function applyLayout() {
    root.dataset.layout = layout;
    root.classList.toggle('is-datasheet', layout === 'datasheet');

    for (const group of layoutSwitches) {
      for (const radio of group.querySelectorAll<HTMLInputElement>('input')) {
        radio.checked = radio.value === layout;
      }
    }

    for (const part of root.querySelectorAll<HTMLElement>('[data-only-layout]')) {
      part.hidden = part.dataset.onlyLayout !== layout;
    }

    options.onLayout(layout);
  }

  for (const group of switches) {
    group.addEventListener('change', (event) => {
      const value = (event.target as HTMLInputElement).value;

      if (!isMode(value)) return;

      wanted = value;
      chosen = true;
      if (canEdit && memory) rememberMode(memory.tenantId, memory.entityId, value);
      apply();
      announce(`${value.charAt(0).toUpperCase()}${value.slice(1)} mode`);
    });
  }

  for (const group of layoutSwitches) {
    group.addEventListener('change', (event) => {
      const value = (event.target as HTMLInputElement).value;

      if (!isLayout(value)) return;

      layout = value;
      applyLayout();
      announce(value === 'datasheet' ? 'Datasheet layout' : 'Sheet layout');
    });
  }

  closeDetails.addEventListener('click', () => {
    detailsOpen = false;
    apply();
  });

  // The band stays in view; it shrinks and shows the name while the header is out of view.
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(([entry]) => {
      bar.classList.toggle('is-compact', !(entry?.isIntersecting ?? true));
    }).observe(head);
  }

  apply();
  applyLayout();

  return {
    allowEdit(allowed, tenantId, entityId) {
      canEdit = allowed;
      memory = { tenantId, entityId };
      if (allowed && !chosen) wanted = savedMode(tenantId, entityId);
      // A mode chosen before it was known who may change the being is kept for next time.
      if (allowed && chosen) rememberMode(tenantId, entityId, wanted);
      apply();
    },
    mode: shown,
    layout: () => layout,
    announce,
    setGmWord(title) {
      gmWord = title;
      apply();
    },
    toggleDetails() {
      if (!canEdit) return;
      // Details are edited in Read, where the being's other edit controls are.
      if (wanted === 'play') wanted = 'read';
      detailsOpen = !detailsOpen;
      apply();
      if (detailsOpen) {
        root.querySelector<HTMLElement>('[data-details]')?.scrollIntoView({ block: 'nearest' });
      }
    },
    setSteps(count, last) {
      undoLast.textContent = last ?? '';
      historyCount.textContent = String(count);
      historyCount.hidden = count === 0;
    },
    setName(name) {
      barName.textContent = name;
    },
  };
}
