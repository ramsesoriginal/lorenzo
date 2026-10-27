import type { Prim, Scene } from './scene';

export const SVG_NS = 'http://www.w3.org/2000/svg';

export type PaintOptions = {
  /** The drawing's accessible name (the `<title>`). */
  title?: string;
  /** What it shows, for a longer description (the `<desc>`). */
  description?: string;
  /** Prefix of the ids the title and description take; make it unique per `<svg>` on a page. */
  idPrefix?: string;
  /** Overrides the scene's `iconBase`: where `icons.svg` is served from. */
  iconBase?: string;
  /**
   * The ARIA role of the `<svg>`: `img` by default (ADR 0339). Descendants of an `img` can be
   * dropped from the accessibility tree by some browsers; `group` keeps each placement reachable.
   */
  role?: 'img' | 'group';
};

/** A tiny element tree: what both `paintSvg` and `sceneToSvg` are written from. */
export type TreeNode = {
  tag: string;
  attrs: [string, string][];
  /** For a leaf that holds text (`text`, `title`, `desc`): set with `textContent` only. */
  text?: string;
  children: TreeNode[];
};

function node(tag: string, attrs: [string, string][], children: TreeNode[] = []): TreeNode {
  return { tag, attrs, children };
}

function leaf(tag: string, attrs: [string, string][], text: string): TreeNode {
  return { tag, attrs, text, children: [] };
}

function strokeAttrs(prim: Prim): [string, string][] {
  const out: [string, string][] = [];

  if ('strokeWidth' in prim && prim.strokeWidth !== undefined) {
    out.push(['stroke-width', String(prim.strokeWidth)]);
  }

  if ('dash' in prim && prim.dash !== undefined) out.push(['stroke-dasharray', prim.dash]);

  return out;
}

export function iconHref(iconBase: string, icon: string): string {
  return iconBase === '' ? `#icon-${icon}` : `${iconBase}/icons.svg#icon-${icon}`;
}

function primNode(prim: Prim, iconBase: string): TreeNode {
  switch (prim.kind) {
    case 'rect':
      return node('rect', [
        ['class', prim.cls],
        ['x', String(prim.x)],
        ['y', String(prim.y)],
        ['width', String(prim.width)],
        ['height', String(prim.height)],
      ]);
    case 'path': {
      const attrs: [string, string][] = [['class', prim.cls], ['d', prim.d], ...strokeAttrs(prim)];

      if (prim.fillRule) attrs.push(['fill-rule', prim.fillRule]);

      return node('path', attrs);
    }
    case 'circle':
      return node('circle', [
        ['class', prim.cls],
        ['cx', String(prim.cx)],
        ['cy', String(prim.cy)],
        ['r', String(prim.r)],
        ...strokeAttrs(prim),
      ]);
    case 'text': {
      const attrs: [string, string][] = [
        ['class', prim.cls],
        ['x', String(prim.x)],
        ['y', String(prim.y)],
      ];

      if (prim.anchor) attrs.push(['text-anchor', prim.anchor]);

      return leaf('text', attrs, prim.text);
    }
    case 'icon':
      return node('use', [
        ['class', prim.cls],
        ['href', iconHref(iconBase, prim.icon)],
        ['x', String(prim.x)],
        ['y', String(prim.y)],
        ['width', String(prim.size)],
        ['height', String(prim.size)],
      ]);
  }
}

/** The element tree of a Scene: the sheet, then one focusable `<g>` for each placement. */
export function sceneTree(scene: Scene, options: PaintOptions = {}): TreeNode {
  const iconBase = options.iconBase ?? scene.iconBase;
  const prefix = options.idPrefix ?? 'map';
  const children: TreeNode[] = [];
  const labelled: string[] = [];

  if (options.title) {
    children.push(leaf('title', [['id', `${prefix}-title`]], options.title));
    labelled.push(`${prefix}-title`);
  }

  if (options.description) {
    children.push(leaf('desc', [['id', `${prefix}-desc`]], options.description));
    labelled.push(`${prefix}-desc`);
  }

  let group: TreeNode | null = null;
  let groupEntry: string | undefined;

  for (const prim of scene.prims) {
    const el = primNode(prim, iconBase);

    if (prim.entryId === undefined) {
      group = null;
      groupEntry = undefined;
      children.push(el);
      continue;
    }

    if (!group || groupEntry !== prim.entryId) {
      groupEntry = prim.entryId;
      group = node('g', [
        ['class', 'm-mark'],
        ['tabindex', '0'],
        ['role', 'button'],
        ['aria-label', prim.label ?? ''],
        ['aria-pressed', scene.selection === prim.entryId ? 'true' : 'false'],
        ['data-entry', prim.entryId],
      ]);
      children.push(group);
    }

    group.children.push(el);
  }

  const attrs: [string, string][] = [
    ['class', 'm-svg'],
    ['viewBox', `0 0 ${scene.width} ${scene.height}`],
    ['data-theme', scene.theme],
    ['role', options.role ?? 'img'],
  ];

  if (labelled.length > 0) attrs.push(['aria-labelledby', labelled.join(' ')]);

  return node('svg', attrs, children);
}

function escapeText(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function escapeAttr(text: string): string {
  return escapeText(text).replace(/"/g, '&quot;');
}

function serialise(n: TreeNode, root: boolean): string {
  const attrs = [...(root ? ([['xmlns', SVG_NS]] as [string, string][]) : []), ...n.attrs]
    .map(([k, v]) => ` ${k}="${escapeAttr(v)}"`)
    .join('');

  if (n.text !== undefined) return `<${n.tag}${attrs}>${escapeText(n.text)}</${n.tag}>`;

  if (n.children.length === 0) return `<${n.tag}${attrs}/>`;

  return `<${n.tag}${attrs}>${n.children.map((c) => serialise(c, false)).join('')}</${n.tag}>`;
}

/** The markup `paintSvg` makes, as a string with text and attributes escaped. For golden tests. */
export function sceneToSvg(scene: Scene, options: PaintOptions = {}): string {
  return serialise(sceneTree(scene, options), true);
}

function create(doc: Document, n: TreeNode): Element {
  const el = doc.createElementNS(SVG_NS, n.tag);

  for (const [k, v] of n.attrs) el.setAttribute(k, v);

  if (n.text !== undefined) {
    el.textContent = n.text;
  } else {
    for (const child of n.children) el.appendChild(create(doc, child));
  }

  return el;
}

function sync(doc: Document, el: Element, n: TreeNode, root: boolean): void {
  const wanted = new Set<string>();

  for (const [k, v] of n.attrs) {
    wanted.add(k);

    if (el.getAttribute(k) !== v) el.setAttribute(k, v);
  }

  // The root keeps attributes the caller set itself (a tabindex, a data-cursor).
  if (!root) {
    for (const name of el.getAttributeNames()) {
      if (!wanted.has(name)) el.removeAttribute(name);
    }
  }

  if (n.text !== undefined) {
    if (el.textContent !== n.text) el.textContent = n.text;

    return;
  }

  const have = el.children;

  for (let i = 0; i < n.children.length; i += 1) {
    const want = n.children[i];
    const current = have[i];

    if (!want) continue;

    if (!current) {
      el.appendChild(create(doc, want));
    } else if (current.tagName.toLowerCase() !== want.tag) {
      el.replaceChild(create(doc, want), current);
    } else {
      sync(doc, current, want, false);
    }
  }

  while (el.children.length > n.children.length) {
    const last = el.lastElementChild;

    if (!last) break;

    el.removeChild(last);
  }
}

/**
 * Draws a Scene into an `<svg>` with `createElementNS`, `setAttribute` and `textContent` only,
 * never `innerHTML`: a name a person wrote is text, never parsed. Calling it again with a newer
 * Scene updates the elements in place, so a focused mark stays focused while the map is panned.
 */
export function paintSvg(scene: Scene, svg: SVGSVGElement, options: PaintOptions = {}): void {
  sync(svg.ownerDocument, svg, sceneTree(scene, options), true);
}
