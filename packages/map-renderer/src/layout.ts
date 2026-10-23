import { bboxOf, finitePoint, flattenCubic, growBBox, num } from './geom';
import { project, toScreen, transformOf } from './project';
import type { Hit, Prim, Scene } from './scene';
import type { DrawableShape, Mark, Shape, Theme, ThemeContext } from './theme';
import { defaultTheme } from './themes/default';
import {
  type BBox,
  groupOf,
  type MapModel,
  normaliseRole,
  type Part,
  type Placement,
  type Point,
  ROLE_WORDS,
  type Role,
  type View,
} from './types';

/** The class a selected or hovered mark takes. It never changes a shape or an icon. */
export const SELECTED_CLASS = 'm-on';
export const HOVER_CLASS = 'm-hover';

/** How far a line is found from, in pixels, at least. */
export const LINE_TOLERANCE = 8;
/** What an estimate of a label's width assumes, per character, for 13px text. */
const CHAR_WIDTH = 7;

function sp(p: Point): Point {
  return [num(p[0]), num(p[1])];
}

function pairs(points: readonly Point[]): string {
  return points.map((p) => `${p[0]} ${p[1]}`).join(' L ');
}

function ringPath(ring: readonly Point[]): string {
  return `M ${pairs(ring)} Z`;
}

function boxOf(points: readonly Point[]): BBox {
  const b = bboxOf(points);

  return [num(b[0]), num(b[1]), num(b[2]), num(b[3])];
}

/** One part of a placement on the screen, or null when it has too little to draw. */
function buildShape(
  part: Part,
  place: (p: Point, what: string) => Point,
  scale: number,
): Shape | null {
  switch (part.shape) {
    case 'point':
      return { kind: 'point', at: place(part.at, 'a point') };

    case 'circle': {
      const r = num(part.r * scale, 'a radius');
      const at = place(part.at, 'a circle');

      if (!(part.r > 0)) return null;

      return { kind: 'circle', at, r };
    }

    case 'polyline': {
      if (part.pts.length < 2) return null;

      const pts = part.pts.map((p) => place(p, 'a polyline point'));

      return { kind: 'line', d: `M ${pairs(pts)}`, bbox: boxOf(pts) };
    }

    case 'bezier': {
      if (part.segs.length === 0) return null;

      const start = place(part.start, 'a bezier start');
      const all: Point[] = [start];
      let d = `M ${start[0]} ${start[1]}`;
      let at = start;

      for (const seg of part.segs) {
        const c1 = place(seg[0], 'a bezier control');
        const c2 = place(seg[1], 'a bezier control');
        const end = place(seg[2], 'a bezier end');

        d += ` C ${c1[0]} ${c1[1]} ${c2[0]} ${c2[1]} ${end[0]} ${end[1]}`;
        all.push(...flattenCubic(at, c1, c2, end));
        at = end;
      }

      if (part.closed) return { kind: 'area', d: `${d} Z`, bbox: boxOf(all) };

      return { kind: 'line', d, bbox: boxOf(all) };
    }

    case 'polygon': {
      const rings = part.rings
        .filter((ring) => ring.length >= 3)
        .map((ring) => ring.map((p) => place(p, 'a polygon point')));

      if (rings.length === 0 || part.rings[0] === undefined || part.rings[0].length < 3) {
        return null;
      }

      return {
        kind: 'area',
        d: rings.map(ringPath).join(' '),
        bbox: boxOf(rings.flat()),
      };
    }

    default:
      // A shape this version does not know: nothing is drawn.
      return null;
  }
}

function classes(base: string, entryId: string | undefined, view: View): string {
  if (entryId === undefined) return base;

  let cls = base;

  if (view.selection === entryId) cls += ` ${SELECTED_CLASS}`;

  if (view.hover === entryId) cls += ` ${HOVER_CLASS}`;

  return cls;
}

function hitFor(mark: Extract<Mark, { type: 'draw' }>): Hit | undefined {
  if (!mark.hit) return undefined;

  if (mark.shape.kind === 'line') {
    return {
      mode: 'line',
      tol: num(Math.max(LINE_TOLERANCE, (mark.width ?? 0) / 2), 'a tolerance'),
    };
  }

  return { mode: 'area' };
}

function primOf(mark: Mark, id: string, entryId: string, view: View): Prim {
  switch (mark.type) {
    case 'draw': {
      const shape: DrawableShape = mark.shape;
      const half = (mark.width ?? 0) / 2;
      const hit = hitFor(mark);
      const base = {
        id,
        cls: classes(mark.cls, entryId, view),
        entryId,
        ...(hit ? { hit } : {}),
      };
      const stroke = {
        ...(mark.width === undefined ? {} : { strokeWidth: num(mark.width, 'a stroke width') }),
        ...(mark.dash === undefined ? {} : { dash: mark.dash }),
      };

      if (shape.kind === 'circle') {
        const [cx, cy] = sp(shape.at);
        const r = num(shape.r, 'a radius');

        return {
          ...base,
          ...stroke,
          kind: 'circle',
          cx,
          cy,
          r,
          bbox: [num(cx - r - half), num(cy - r - half), num(cx + r + half), num(cy + r + half)],
        };
      }

      const grown = growBBox(shape.bbox, half);

      return {
        ...base,
        ...stroke,
        kind: 'path',
        d: shape.d,
        ...(shape.kind === 'area' ? { fillRule: 'evenodd' as const } : {}),
        bbox: [num(grown[0]), num(grown[1]), num(grown[2]), num(grown[3])],
      };
    }

    case 'text': {
      const [x, y] = sp(mark.at);
      const width = mark.text.length * CHAR_WIDTH;
      const x0 = mark.anchor === 'middle' ? x - width / 2 : x;

      return {
        id,
        kind: 'text',
        cls: classes(mark.cls, entryId, view),
        entryId,
        x,
        y,
        text: mark.text,
        ...(mark.anchor ? { anchor: mark.anchor } : {}),
        bbox: [num(x0), num(y - 12), num(x0 + width), num(y + 4)],
      };
    }

    case 'icon': {
      const [cx, cy] = sp(mark.at);
      const x = num(cx - mark.size / 2);
      const y = num(cy - mark.size / 2);
      const size = num(mark.size, 'an icon size');

      return {
        id,
        kind: 'icon',
        cls: classes(mark.cls, entryId, view),
        entryId,
        icon: mark.icon,
        x,
        y,
        size,
        bbox: [x, y, num(x + size), num(y + size)],
      };
    }
  }
}

function compareText(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

/**
 * What a mark is called: the name and the role in words. Words drawn in the mark that the name
 * does not hold, such as a person's initials, are part of it too (WCAG 2.5.3, label in name).
 */
function accessibleName(placement: Placement, role: Role | null, drawn: readonly string[]): string {
  const name = placement.entry.name;
  const lower = name.toLowerCase();
  const extra = drawn.filter((text) => !lower.includes(text.toLowerCase()));
  const named = extra.length > 0 ? `${name}, ${extra.join(' ')}` : name;

  return role ? `${named}, ${ROLE_WORDS[role]}` : named;
}

/**
 * The Scene of a Map for a view: pure, so the same input is the same bytes. Everything is in the
 * screen pixels of the viewport (draw it with `viewBox="0 0 width height"` and no transform), and
 * every number is rounded to two decimals. A number that is not finite throws.
 */
export function layout(model: MapModel, view: View, theme: Theme = defaultTheme): Scene {
  const t = transformOf(model.system, view);
  const { width, height } = t;
  const system = model.system;

  const place = (p: Point, what: string): Point =>
    sp(toScreen(t, project(system, finitePoint(p, what))));

  const ctx: ThemeContext = {
    system,
    scale: t.scale,
    design: t.scale * t.designUnit,
    designUnit: t.designUnit,
    names: view.groups.names,
    showPlaces: view.groups.showPlaces,
    toScreen: (p) => toScreen(t, project(system, finitePoint(p, 'a point'))),
    cubic: (p0, p1, p2, p3) => {
      const a = place(p0, 'a cubic start');
      const b = place(p1, 'a cubic control');
      const c = place(p2, 'a cubic control');
      const e = place(p3, 'a cubic end');

      return {
        kind: 'line',
        d: `M ${a[0]} ${a[1]} C ${b[0]} ${b[1]} ${c[0]} ${c[1]} ${e[0]} ${e[1]}`,
        bbox: boxOf([a, ...flattenCubic(a, b, c, e)]),
      };
    },
  };

  const visible = model.placements
    .map((placement) => {
      const role = normaliseRole(placement.role);

      return { placement, role, layer: theme.layer(placement, role) };
    })
    .filter(({ role }) => view.groups[groupOf(role)])
    .sort(
      (a, b) =>
        a.layer - b.layer ||
        a.placement.z - b.placement.z ||
        compareText(a.placement.entry.id, b.placement.entry.id),
    );

  const prims: Prim[] = [
    {
      id: 'sheet',
      kind: 'rect',
      cls: theme.sheetClass,
      x: 0,
      y: 0,
      width: num(width),
      height: num(height),
      bbox: [0, 0, num(width), num(height)],
    },
  ];

  for (const { placement, role } of visible) {
    const entryId = placement.entry.id;
    const ids = new Map<string, number>();
    const first = prims.length;

    placement.geometry.parts.forEach((part, partIndex) => {
      const shape = buildShape(part, place, t.scale);

      if (!shape) return;

      for (const mark of theme.marks({ placement, role, part, partIndex, shape, ctx })) {
        const base = `${entryId}:${partIndex}:${mark.purpose}`;
        const seen = ids.get(base) ?? 0;

        ids.set(base, seen + 1);
        prims.push(primOf(mark, seen === 0 ? base : `${base}#${seen}`, entryId, view));
      }
    });

    const lead = prims[first];

    if (lead) {
      const drawn = prims.slice(first).flatMap((prim) => (prim.kind === 'text' ? [prim.text] : []));

      lead.label = accessibleName(placement, role, drawn);
    }
  }

  return {
    theme: theme.name,
    width: num(width),
    height: num(height),
    selection: view.selection,
    iconBase: view.iconBase ?? '',
    prims,
  };
}
