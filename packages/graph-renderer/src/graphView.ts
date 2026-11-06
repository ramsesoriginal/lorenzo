// The DOM around the three steps: one <svg> in a host, pan and zoom by pointer and keys, select,
// centre on, and move a node by hand in `manual`. It emits events; it never fetches or writes.

import { hitTest } from './hit';
import {
  type ArrowKey,
  centreOn as centred,
  moveAlongEdges,
  panBy,
  toWorld,
  zoomAt,
} from './interaction';
import { layout } from './layout';
import { paintSvg } from './paint';
import { themeFor } from './themes';
import {
  DEFAULT_VIEW,
  type GraphModel,
  type GraphView,
  type Point,
  type Scene,
  type Selection,
} from './types';

export interface GraphViewOptions {
  model: GraphModel;
  title: string;
  iconBase?: string;
  view?: Partial<GraphView>;
  /** The viewer's theme choice; a web's hint and the default follow it. */
  theme?: string | null;
  themeHint?: string | null;
  onSelect?: (selection: Selection) => void;
  /** Enter on a node: open it. */
  onOpen?: (id: string) => void;
  /** A node moved by hand (only in `manual`), in layout units. */
  onMove?: (id: string, at: Point) => void;
}

export interface GraphViewHandle {
  setModel(model: GraphModel): void;
  setView(view: Partial<GraphView>): void;
  getView(): GraphView;
  getScene(): Scene;
  select(selection: Selection): void;
  centreOn(id: string): void;
  zoomIn(): void;
  zoomOut(): void;
  resize(width: number, height: number): void;
  destroy(): void;
}

const NS = 'http://www.w3.org/2000/svg';

export function createGraphView(host: HTMLElement, options: GraphViewOptions): GraphViewHandle {
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('class', 'gr-svg');
  host.appendChild(svg);
  let model = options.model;
  let view: GraphView = {
    ...DEFAULT_VIEW,
    width: host.clientWidth || DEFAULT_VIEW.width,
    height: host.clientHeight || DEFAULT_VIEW.height,
    ...options.view,
  };
  let scene = layout(model, view, themeFor(options.theme, options.themeHint));

  const redraw = () => {
    scene = layout(model, view, themeFor(options.theme, options.themeHint));
    paintSvg(scene, svg, {
      title: options.title,
      ...(options.iconBase === undefined ? {} : { iconBase: options.iconBase }),
    });
  };
  const local = (event: PointerEvent): Point => {
    const box = svg.getBoundingClientRect();
    return {
      x: ((event.clientX - box.left) / (box.width || 1)) * scene.width,
      y: ((event.clientY - box.top) / (box.height || 1)) * scene.height,
    };
  };
  const select = (next: Selection) => {
    view = { ...view, selection: next };
    redraw();
    options.onSelect?.(next);
  };

  let drag: { at: Point; node: string | null; moved: boolean } | null = null;
  const onDown = (event: PointerEvent) => {
    const at = local(event);
    const hit = hitTest(scene, at);
    drag = { at, node: hit?.kind === 'node' ? hit.id : null, moved: false };
    svg.setPointerCapture(event.pointerId);
    svg.dataset.cursor = 'grabbing';
  };
  const onMove = (event: PointerEvent) => {
    if (!drag) return;
    const at = local(event);
    const dx = at.x - drag.at.x;
    const dy = at.y - drag.at.y;
    if (!drag.moved && Math.abs(dx) + Math.abs(dy) < 4) return;
    drag.moved = true;
    if (drag.node && view.layout === 'manual') {
      const world = toWorld(scene, at);
      view = { ...view, positions: { ...view.positions, [drag.node]: world } };
    } else {
      view = panBy(view, dx, dy);
      drag.at = at;
    }
    redraw();
  };
  const onUp = (event: PointerEvent) => {
    if (!drag) return;
    const finished = drag;
    drag = null;
    delete svg.dataset.cursor;
    if (!finished.moved) {
      const hit = hitTest(scene, local(event));
      select(hit && hit.kind !== 'group' ? { kind: hit.kind, id: hit.id } : null);
    } else if (finished.node && view.layout === 'manual') {
      const at = view.positions?.[finished.node];
      if (at) options.onMove?.(finished.node, at);
    }
  };
  const onWheel = (event: WheelEvent) => {
    event.preventDefault();
    const box = svg.getBoundingClientRect();
    const at = {
      x: ((event.clientX - box.left) / (box.width || 1)) * scene.width,
      y: ((event.clientY - box.top) / (box.height || 1)) * scene.height,
    };
    view = zoomAt(view, event.deltaY < 0 ? 1.15 : 1 / 1.15, at);
    redraw();
  };
  const onKey = (event: KeyboardEvent) => {
    const target = (event.target as Element).closest('[data-node-id]');
    const id = target?.getAttribute('data-node-id') ?? null;
    if (event.key === 'Escape') {
      select(null);
    } else if (id && event.key === 'Enter') {
      event.preventDefault();
      select({ kind: 'node', id });
      options.onOpen?.(id);
    } else if (id && event.key === ' ') {
      event.preventDefault();
      select({ kind: 'node', id });
    } else if (id && event.key.startsWith('Arrow')) {
      const next = moveAlongEdges(scene, model, id, event.key as ArrowKey);
      if (next) {
        event.preventDefault();
        svg.querySelector<SVGElement>(`[data-node-id="${CSS.escape(next)}"]`)?.focus();
      }
    } else if (event.key === '+' || event.key === '=') {
      view = zoomAt(view, 1.2, { x: view.width / 2, y: view.height / 2 });
      redraw();
    } else if (event.key === '-') {
      view = zoomAt(view, 1 / 1.2, { x: view.width / 2, y: view.height / 2 });
      redraw();
    }
  };
  svg.addEventListener('pointerdown', onDown);
  svg.addEventListener('pointermove', onMove);
  svg.addEventListener('pointerup', onUp);
  svg.addEventListener('wheel', onWheel, { passive: false });
  svg.addEventListener('keydown', onKey);
  redraw();

  return {
    setModel(next) {
      model = next;
      redraw();
    },
    setView(next) {
      view = { ...view, ...next };
      redraw();
    },
    getView: () => view,
    getScene: () => scene,
    select,
    centreOn(id) {
      view = centred(scene, view, id);
      redraw();
    },
    zoomIn() {
      view = zoomAt(view, 1.2, { x: view.width / 2, y: view.height / 2 });
      redraw();
    },
    zoomOut() {
      view = zoomAt(view, 1 / 1.2, { x: view.width / 2, y: view.height / 2 });
      redraw();
    },
    resize(width, height) {
      view = { ...view, width, height };
      redraw();
    },
    destroy() {
      svg.removeEventListener('pointerdown', onDown);
      svg.removeEventListener('pointermove', onMove);
      svg.removeEventListener('pointerup', onUp);
      svg.removeEventListener('wheel', onWheel);
      svg.removeEventListener('keydown', onKey);
      svg.remove();
    },
  };
}
