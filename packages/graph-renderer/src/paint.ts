// Step two: paintSvg(scene, svg). `createElementNS`, `setAttribute` and `textContent` only: text a
// person wrote is never parsed. Called again it updates in place, so a focused node stays focused
// (ADR 0407).

import type { Primitive, Scene } from './types';

const NS = 'http://www.w3.org/2000/svg';

export interface PaintOptions {
  /** The accessible name of the whole drawing. */
  title: string;
  /** Where the brand's icons.svg is served from. */
  iconBase?: string;
}

type Layers = { hulls: SVGGElement; edges: SVGGElement; nodes: SVGGElement };
const state = new WeakMap<SVGSVGElement, { layers: Layers; seen: Map<string, Element> }>();

function make<K extends keyof SVGElementTagNameMap>(
  svg: SVGSVGElement,
  tag: K,
): SVGElementTagNameMap[K] {
  return svg.ownerDocument.createElementNS(NS, tag);
}

function layersOf(svg: SVGSVGElement) {
  let held = state.get(svg);
  if (!held) {
    const layers: Layers = { hulls: make(svg, 'g'), edges: make(svg, 'g'), nodes: make(svg, 'g') };
    layers.hulls.setAttribute('data-layer', 'hulls');
    layers.edges.setAttribute('data-layer', 'edges');
    layers.nodes.setAttribute('data-layer', 'nodes');
    svg.replaceChildren(layers.hulls, layers.edges, layers.nodes);
    held = { layers, seen: new Map() };
    state.set(svg, held);
  }
  return held;
}

/** Takes the element kept under `id`, or makes it and puts it in `parent` at `index`. */
function keep<E extends Element>(
  seen: Map<string, Element>,
  parent: Element,
  id: string,
  create: () => E,
  index: number,
  alive: Set<string>,
): E {
  let el = seen.get(id) as E | undefined;
  if (!el) {
    el = create();
    el.setAttribute('data-id', id);
    seen.set(id, el);
  }
  alive.add(id);
  if (parent.children[index] !== el) parent.insertBefore(el, parent.children[index] ?? null);
  return el;
}

function setMarks(el: Element, p: Extract<Primitive, { className: string }>) {
  const classes = [p.className];
  if ('selected' in p && p.selected) classes.push('is-selected');
  if ('dim' in p && p.dim) classes.push('is-dim');
  el.setAttribute('class', classes.join(' '));
}

export function paintSvg(scene: Scene, svg: SVGSVGElement, options: PaintOptions): void {
  const { layers, seen } = layersOf(svg);
  svg.setAttribute('viewBox', `0 0 ${scene.width} ${scene.height}`);
  svg.setAttribute('role', 'group');
  svg.setAttribute('aria-label', options.title);
  const alive = new Set<string>();
  const counts = { hulls: 0, edges: 0, nodes: 0 };
  // Each node is one focusable button holding its disc, icon and label.
  const nodeGroups = new Map<string, SVGGElement>();
  const inGroup = new Map<string, number>();
  for (const p of scene.primitives) {
    if (p.source.kind === 'node') {
      let group = nodeGroups.get(p.source.id);
      if (!group) {
        group = keep(
          seen,
          layers.nodes,
          `node-group:${p.source.id}`,
          () => make(svg, 'g'),
          counts.nodes,
          alive,
        );
        counts.nodes += 1;
        group.setAttribute('role', 'button');
        group.setAttribute('tabindex', '0');
        nodeGroups.set(p.source.id, group);
      }
      const group_ = group;
      const index = inGroup.get(p.source.id) ?? 0;
      inGroup.set(p.source.id, index + 1);
      if (p.kind === 'circle') {
        group_.setAttribute('aria-label', p.name);
        group_.setAttribute('aria-pressed', p.selected ? 'true' : 'false');
        group_.setAttribute('data-node-id', p.source.id);
        const el = keep(seen, group_, p.id, () => make(svg, 'circle'), index, alive);
        el.setAttribute('cx', String(p.cx));
        el.setAttribute('cy', String(p.cy));
        el.setAttribute('r', String(p.r));
        setMarks(el, p);
      } else if (p.kind === 'icon') {
        const el = keep(seen, group_, p.id, () => make(svg, 'use'), index, alive);
        el.setAttribute('href', `${options.iconBase ?? ''}#icon-${p.key}`);
        el.setAttribute('x', String(p.x));
        el.setAttribute('y', String(p.y));
        el.setAttribute('width', String(p.size));
        el.setAttribute('height', String(p.size));
        el.setAttribute('class', 'gr-icon');
        el.setAttribute('aria-hidden', 'true');
      } else if (p.kind === 'text') {
        const el = keep(seen, group_, p.id, () => make(svg, 'text'), index, alive);
        el.setAttribute('x', String(p.x));
        el.setAttribute('y', String(p.y));
        el.setAttribute('text-anchor', 'middle');
        el.setAttribute('class', p.className);
        el.setAttribute('aria-hidden', 'true');
        el.textContent = p.text;
      }
      continue;
    }
    if (p.kind === 'path') {
      const layer = p.role === 'hull' ? layers.hulls : layers.edges;
      const slot = p.role === 'hull' ? counts.hulls++ : counts.edges++;
      const el = keep(seen, layer, p.id, () => make(svg, 'path'), slot, alive);
      el.setAttribute('d', p.d);
      if (p.role === 'arrow') {
        el.removeAttribute('stroke-dasharray');
      } else {
        el.setAttribute('stroke-width', String(p.width));
        if (p.dash) el.setAttribute('stroke-dasharray', p.dash);
        else el.removeAttribute('stroke-dasharray');
      }
      el.setAttribute('data-source', p.source.id);
      setMarks(el, p);
    } else if (p.kind === 'text') {
      const layer = p.role === 'hull-label' ? layers.hulls : layers.edges;
      const slot = p.role === 'hull-label' ? counts.hulls++ : counts.edges++;
      const el = keep(seen, layer, p.id, () => make(svg, 'text'), slot, alive);
      el.setAttribute('x', String(p.x));
      el.setAttribute('y', String(p.y));
      el.setAttribute('text-anchor', 'middle');
      el.setAttribute('class', p.className);
      el.setAttribute('aria-hidden', 'true');
      el.textContent = p.text;
    }
  }
  for (const [id, el] of [...seen]) {
    if (!alive.has(id)) {
      el.remove();
      seen.delete(id);
    }
  }
}
