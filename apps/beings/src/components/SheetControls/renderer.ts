// The frame of a being's sheet (RFC 0043, BN2, BN7): the mode, the order of the sections, the band
// that keeps the mode switch, what the mode is for and the pinned numbers in view (it shrinks and
// shows the name once the header has scrolled away), and the one small live region that says what
// changed. It draws no content itself.

import {
  isLayout,
  isMode,
  type Layout,
  MODE_LINES,
  type Mode,
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
  /** Shows these as the numbers kept in the sticky bar. */
  setVitals(vitals: { label: string; value: string }[]): void;
  setName(name: string): void;
};

const required = requiredIn('Sheet controls');

export function renderSheetControls(options: SheetControlsOptions): RenderedSheetControls {
  const { root } = options;
  const head = required<HTMLElement>(root, '[data-sheet-head]');
  const bar = required<HTMLElement>(root, '[data-sticky]');
  const barName = required<HTMLElement>(bar, '[data-sticky-name]');
  const vitals = required<HTMLElement>(bar, '[data-vitals]');
  const main = required<HTMLElement>(root, '[data-sheet-main]');
  const live = required<HTMLElement>(root, '[data-live]');
  const switches = [...root.querySelectorAll<HTMLElement>('[data-mode-switch]')];
  const layoutSwitches = [...root.querySelectorAll<HTMLElement>('[data-layout-switch]')];

  const modeLine = required<HTMLElement>(root, '[data-mode-line]');
  const detailsButton = required<HTMLButtonElement>(root, '[data-edit-details]');

  let wanted: Mode = 'read';
  let layout: Layout = 'sheet';
  let canEdit = false;
  let detailsOpen = false;
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

    modeLine.textContent = MODE_LINES[mode];

    // The order of the sections follows the mode.
    for (const [index, name] of sectionOrder(mode).entries()) {
      const section = main.querySelector<HTMLElement>(`[data-section="${name}"]`);

      if (section) section.style.order = String(index);
    }

    // What changes the being is for Read, and for whoever may change it; Play has none of it.
    const editing = canEdit && mode === 'read';

    if (!editing) detailsOpen = false;
    detailsButton.hidden = !editing;
    detailsButton.setAttribute('aria-expanded', String(detailsOpen));
    detailsButton.textContent = detailsOpen ? 'Done editing details' : 'Edit details';

    for (const part of root.querySelectorAll<HTMLElement>('[data-only-in]')) {
      part.hidden = !(editing && (part.dataset.onlyIn ?? '') === 'edit');
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

  detailsButton.addEventListener('click', () => {
    detailsOpen = !detailsOpen;
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
    setVitals(values) {
      vitals.replaceChildren(
        ...values.map(({ label, value }) => {
          const item = document.createElement('span');
          const name = document.createElement('span');
          const number = document.createElement('strong');

          item.className = 'band-number';
          name.className = 'caption';
          name.textContent = label;
          number.textContent = value;
          item.append(name, ' ', number);

          return item;
        }),
      );
    },
    setName(name) {
      barName.textContent = name;
    },
  };
}
