import { placementCentre } from './geom';
import { hitTest } from './hit';
import { layout } from './layout';
import { type PaintOptions, paintSvg, SVG_NS } from './paint';
import type { Scene } from './scene';
import type { Theme } from './theme';
import { defaultTheme } from './themes/default';
import { DEFAULT_GROUPS, type Groups, type MapModel, type Point, type View } from './types';
import {
  centreOn,
  fitView,
  PAN_STEP,
  panBy,
  type Viewport,
  type ViewState,
  ZOOM_STEP,
  zoomBy,
  zoomTo,
} from './view';

export type MapViewOptions = {
  model: MapModel;
  /** The drawing's accessible name. */
  title: string;
  /** What it shows, for the accessible description. */
  description?: string;
  theme?: Theme;
  /** Which groups are on to begin with; every one is on by default. */
  groups?: Partial<Groups>;
  selection?: string | null;
  /** Where the brand's `icons.svg` is served from. */
  iconBase?: string;
  /** The ARIA role of the drawing; see `PaintOptions.role`. */
  role?: PaintOptions['role'];
  /** A person selected or cleared the selection by clicking, tapping or pressing a key. */
  onSelect?: (entryId: string | null) => void;
  /** The zoom or the centre changed, by a gesture or by a method. */
  onView?: (view: { zoom: number; centre: Point }) => void;
  /** The pointer or the focus moved onto a placement, or off all. */
  onHover?: (entryId: string | null) => void;
};

export type MapViewState = {
  zoom: number;
  centre: Point;
  groups: Groups;
  selection: string | null;
  hover: string | null;
};

export interface MapViewController {
  /** The `<svg>` this view draws into. */
  readonly svg: SVGSVGElement;
  /** Swaps in a new Map; the view (zoom, centre) is kept, call `fit()` to reset it. */
  setModel(model: MapModel): void;
  setGroups(groups: Partial<Groups>): void;
  /** Marks a placement as hovered (a class, never a change of shape). Does not call `onHover`. */
  setHover(entryId: string | null): void;
  /** Selects a placement or clears the selection. Does not call `onSelect`. */
  select(entryId: string | null): void;
  /** "Whole map". */
  fit(): void;
  zoomIn(): void;
  zoomOut(): void;
  /** Sets the zoom (clamped to 0.25 to 16) about the centre. */
  zoomTo(zoom: number): void;
  /** Puts a placement's centre in the middle; false when the entry has no drawn part. */
  centreOn(entryId: string): boolean;
  getView(): MapViewState;
  /** The Scene last drawn, or null before the host has a size. */
  scene(): Scene | null;
  /** Removes the listeners and the `<svg>`. */
  destroy(): void;
}

/** Pointer travel, in pixels, before a press is a drag and not a click. */
const DRAG_THRESHOLD = 4;
let counter = 0;

function entryOf(target: EventTarget | null): string | null {
  const el = target as Element | null;

  if (!el || typeof el.closest !== 'function') return null;

  return el.closest('[data-entry]')?.getAttribute('data-entry') ?? null;
}

/**
 * The interaction around the drawing: it makes the `<svg>`, keeps a view, draws with `layout` and
 * `paintSvg` when something changed (once per animation frame), and turns pointer, wheel and key
 * input into a pan, a zoom or a selection. It never fetches, writes or stores anything; the app
 * decides what a selection opens. The host needs a definite size (the drawing fills it).
 */
export function createMapView(host: HTMLElement, options: MapViewOptions): MapViewController {
  const doc = host.ownerDocument;
  const win = doc.defaultView;
  const theme = options.theme ?? defaultTheme;
  const idPrefix = `map-${++counter}`;
  const svg = doc.createElementNS(SVG_NS, 'svg') as SVGSVGElement;

  let model = options.model;
  let state: ViewState = fitView(model.system);
  let groups: Groups = { ...DEFAULT_GROUPS, ...options.groups };
  let selection = options.selection ?? null;
  let hover: string | null = null;
  let scene: Scene | null = null;
  let cancelFrame: (() => void) | null = null;
  let destroyed = false;
  let drag: {
    id: number;
    x: number;
    y: number;
    lastX: number;
    lastY: number;
    moved: boolean;
  } | null = null;
  let suppressClick = false;

  svg.setAttribute('tabindex', '0');
  svg.setAttribute('data-cursor', 'grab');
  host.appendChild(svg);

  const viewport = (): Viewport => ({ width: host.clientWidth, height: host.clientHeight });

  function redraw(): void {
    cancelFrame = null;

    if (destroyed) return;

    const vp = viewport();

    if (!(vp.width > 0) || !(vp.height > 0)) return;

    const view: View = {
      viewport: vp,
      zoom: state.zoom,
      centre: state.centre,
      groups,
      selection,
      hover,
      ...(options.iconBase === undefined ? {} : { iconBase: options.iconBase }),
    };

    scene = layout(model, view, theme);
    paintSvg(scene, svg, {
      title: options.title,
      idPrefix,
      ...(options.description === undefined ? {} : { description: options.description }),
      ...(options.role === undefined ? {} : { role: options.role }),
    });
  }

  function schedule(): void {
    if (cancelFrame || destroyed) return;

    if (win && typeof win.requestAnimationFrame === 'function') {
      const handle = win.requestAnimationFrame(redraw);

      cancelFrame = () => win.cancelAnimationFrame(handle);
    } else {
      const handle = setTimeout(redraw, 0);

      cancelFrame = () => clearTimeout(handle);
    }
  }

  function setView(next: ViewState): void {
    if (
      next.zoom === state.zoom &&
      next.centre[0] === state.centre[0] &&
      next.centre[1] === state.centre[1]
    ) {
      return;
    }

    state = next;
    schedule();
    options.onView?.({ zoom: state.zoom, centre: state.centre });
  }

  function setHover(id: string | null, emit: boolean): void {
    if (id === hover) return;

    hover = id;
    schedule();

    if (emit) options.onHover?.(id);
  }

  function pick(id: string | null): void {
    if (id === selection) return;

    selection = id;
    schedule();
    options.onSelect?.(id);
  }

  function pointOf(e: MouseEvent): Point {
    const rect = svg.getBoundingClientRect();
    const vp = viewport();
    const sx = rect.width > 0 ? vp.width / rect.width : 1;
    const sy = rect.height > 0 ? vp.height / rect.height : 1;

    return [(e.clientX - rect.left) * sx, (e.clientY - rect.top) * sy];
  }

  function cursor(value: 'grab' | 'grabbing' | 'pointer'): void {
    if (svg.getAttribute('data-cursor') !== value) svg.setAttribute('data-cursor', value);
  }

  const listeners: [string, EventListener, AddEventListenerOptions | undefined][] = [];

  function on<K extends keyof HTMLElementEventMap>(
    type: K,
    handler: (e: HTMLElementEventMap[K]) => void,
    opts?: AddEventListenerOptions,
  ): void {
    listeners.push([type, handler as EventListener, opts]);
    svg.addEventListener(type, handler as EventListener, opts);
  }

  on('pointerdown', (e) => {
    if (e.button !== 0) return;

    suppressClick = false;
    drag = {
      id: e.pointerId,
      x: e.clientX,
      y: e.clientY,
      lastX: e.clientX,
      lastY: e.clientY,
      moved: false,
    };
    svg.setPointerCapture?.(e.pointerId);
  });

  on('pointermove', (e) => {
    if (drag && drag.id === e.pointerId) {
      if (!drag.moved && Math.hypot(e.clientX - drag.x, e.clientY - drag.y) < DRAG_THRESHOLD)
        return;

      drag.moved = true;
      cursor('grabbing');
      setView(
        panBy(model.system, viewport(), state, e.clientX - drag.lastX, e.clientY - drag.lastY),
      );
      drag.lastX = e.clientX;
      drag.lastY = e.clientY;

      return;
    }

    const id = scene ? hitTest(scene, pointOf(e)) : null;

    cursor(id ? 'pointer' : 'grab');
    setHover(id, true);
  });

  const release = (e: PointerEvent): void => {
    if (!drag || drag.id !== e.pointerId) return;

    if (drag.moved) suppressClick = true;

    drag = null;
    svg.releasePointerCapture?.(e.pointerId);
    cursor('grab');
  };

  on('pointerup', release);
  on('pointercancel', release);
  on('pointerleave', () => {
    if (!drag) {
      cursor('grab');
      setHover(null, true);
    }
  });

  on('click', (e) => {
    if (suppressClick) {
      suppressClick = false;

      return;
    }

    // A click with no detail was made by a keyboard or an assistive technology, which has no
    // pointer position: it names the mark by the element it landed on.
    pick(e.detail === 0 ? entryOf(e.target) : scene ? hitTest(scene, pointOf(e)) : null);
  });

  on(
    'wheel',
    (e) => {
      e.preventDefault();

      const unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 400 : 1;
      const factor = Math.min(2, Math.max(0.5, 2 ** (-(e.deltaY * unit) / 300)));

      setView(zoomBy(model.system, viewport(), state, factor, pointOf(e)));
    },
    { passive: false },
  );

  on('keydown', (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    const entry = entryOf(e.target);

    if ((e.key === 'Enter' || e.key === ' ') && entry) {
      e.preventDefault();
      pick(entry);

      return;
    }

    const vp = viewport();

    switch (e.key) {
      case '+':
      case '=':
        setView(zoomBy(model.system, vp, state, ZOOM_STEP));
        break;
      case '-':
      case '_':
        setView(zoomBy(model.system, vp, state, 1 / ZOOM_STEP));
        break;
      case 'ArrowLeft':
        setView(panBy(model.system, vp, state, PAN_STEP, 0));
        break;
      case 'ArrowRight':
        setView(panBy(model.system, vp, state, -PAN_STEP, 0));
        break;
      case 'ArrowUp':
        setView(panBy(model.system, vp, state, 0, PAN_STEP));
        break;
      case 'ArrowDown':
        setView(panBy(model.system, vp, state, 0, -PAN_STEP));
        break;
      case 'Escape':
        pick(null);
        return;
      default:
        return;
    }

    e.preventDefault();
  });

  on('focusin', (e) => setHover(entryOf(e.target), true));
  on('focusout', () => setHover(null, true));

  const observer = win && 'ResizeObserver' in win ? new win.ResizeObserver(() => schedule()) : null;

  observer?.observe(host);
  redraw();

  return {
    svg,
    setModel(next) {
      model = next;
      schedule();
    },
    setGroups(next) {
      groups = { ...groups, ...next };
      schedule();
    },
    setHover(id) {
      setHover(id, false);
    },
    select(id) {
      if (id === selection) return;

      selection = id;
      schedule();
    },
    fit() {
      setView(fitView(model.system));
    },
    zoomIn() {
      setView(zoomBy(model.system, viewport(), state, ZOOM_STEP));
    },
    zoomOut() {
      setView(zoomBy(model.system, viewport(), state, 1 / ZOOM_STEP));
    },
    zoomTo(zoom) {
      setView(zoomTo(model.system, viewport(), state, zoom));
    },
    centreOn(entryId) {
      const placement = model.placements.find((p) => p.entry.id === entryId);
      const at = placement ? placementCentre(placement) : null;

      if (!at) return false;

      setView(centreOn(state, at));

      return true;
    },
    getView() {
      return { zoom: state.zoom, centre: state.centre, groups: { ...groups }, selection, hover };
    },
    scene() {
      return scene;
    },
    destroy() {
      destroyed = true;
      cancelFrame?.();
      cancelFrame = null;
      observer?.disconnect();

      for (const [type, handler, opts] of listeners) svg.removeEventListener(type, handler, opts);

      listeners.length = 0;
      svg.remove();
    },
  };
}
