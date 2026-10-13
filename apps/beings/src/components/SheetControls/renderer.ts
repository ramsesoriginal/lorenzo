// The frame of a being's sheet (RFC 0043): the mode, the order of the sections, the sticky bar that
// keeps the name, a few numbers and the mode switch in view once the header has scrolled away, and
// the one small live region that says what changed. It draws no content itself.

import {
  effectiveMode,
  isLayout,
  isMode,
  type Layout,
  type Mode,
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
  /** Whether the viewer may be offered Edit; a mode already chosen falls back if not. */
  allowEdit(allowed: boolean, reason: string): void;
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

  let wanted: Mode = 'read';
  let layout: Layout = 'sheet';
  let canEdit = false;
  let editReason = 'You can’t edit this being.';

  const shown = (): Mode => effectiveMode(wanted, canEdit);

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
        const label = radio.closest('label');

        if (radio.value === 'edit') {
          radio.disabled = !canEdit;
          if (label) label.title = canEdit ? '' : editReason;
        }
      }
    }

    // The order of the sections follows the mode; Edit keeps Read's, so the page does not jump.
    for (const [index, name] of sectionOrder(mode).entries()) {
      const section = main.querySelector<HTMLElement>(`[data-section="${name}"]`);

      if (section) section.style.order = String(index);
    }

    for (const part of root.querySelectorAll<HTMLElement>('[data-only-in]')) {
      part.hidden = !(part.dataset.onlyIn ?? '').split(' ').includes(mode);
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

  // The bar shows while the header is out of view.
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(([entry]) => {
      bar.hidden = entry?.isIntersecting ?? true;
    }).observe(head);
  }

  apply();
  applyLayout();

  return {
    allowEdit(allowed, reason) {
      canEdit = allowed;
      editReason = reason;
      apply();
    },
    mode: shown,
    layout: () => layout,
    announce,
    setVitals(values) {
      vitals.replaceChildren(
        ...values.map(({ label, value }) => {
          const item = document.createElement('span');
          const number = document.createElement('strong');

          number.textContent = value;
          item.append(`${label} `, number);

          return item;
        }),
      );
    },
    setName(name) {
      barName.textContent = name;
    },
  };
}
