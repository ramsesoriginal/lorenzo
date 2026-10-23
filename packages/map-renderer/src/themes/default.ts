import { reliefArcs } from '../relief';
import type {
  DrawableShape,
  DrawMark,
  Mark,
  MarkInput,
  Shape,
  Theme,
  ThemeContext,
} from '../theme';
import type { Part, Placement, Role, StrokeStyle, Style, Weight } from '../types';

/**
 * The default theme: the Bench design's map (docs/design/bench/screens/15-map.jpg and its
 * prototype), role by role as ADR 0339 lists them. The numbers are the prototype's own.
 */

/** Stroke widths for a placement's `style.weight`, in screen pixels. */
export const WEIGHT_PX: Readonly<Record<Weight, number>> = {
  hairline: 1,
  thin: 1.5,
  regular: 2,
  thick: 3,
  heavy: 5,
};

const DASHED = '6 5';
const DOTTED = '1 7';

/** A river's band and its border, in design units (the prototype's 40 and 46 on a 1000 sheet). */
const BAND = 40;
const BAND_BORDER = 46;

const PIN_R = 15;
const PEOPLE_R = 12;
const ICON_SIZE = 20;
const LABEL_GAP = 3;
/** From a label's centre line to its baseline, for 13px text. */
const LABEL_BASELINE = 4.5;
/** From a disc's centre to the baseline of 10.5px initials. */
const INITIALS_BASELINE = 3.75;
const HAIRLINE = 1;

/** The atlas icon for the first of an entry's kinds that has one; a place otherwise. */
const KIND_ICONS: Readonly<Record<string, string>> = {
  location: 'kind-location',
  being: 'kind-being',
  item: 'kind-item',
  group: 'kind-group',
  fact: 'kind-fact',
  clock: 'kind-clock',
  calendar: 'kind-calendar',
  connection: 'kind-connection',
  event: 'kind-event',
  book: 'kind-book',
  chapter: 'kind-chapter',
  entity: 'kind-entity',
};

export function iconForKinds(kinds: readonly string[]): string {
  for (const kind of kinds) {
    const icon = Object.hasOwn(KIND_ICONS, kind) ? KIND_ICONS[kind] : undefined;

    if (icon) return icon;
  }

  return 'kind-location';
}

/** The first letters of the first two words of a name, upper-cased. */
export function initials(name: string): string {
  const words = name.trim().split(/\s+/u).filter(Boolean);
  const lettered = words.filter((word) => /^[\p{L}\p{N}]/u.test(word));
  const chosen = lettered.length > 0 ? lettered : words;

  return chosen
    .slice(0, 2)
    .map((word) => Array.from(word)[0] ?? '')
    .join('')
    .toUpperCase();
}

function weightOf(style: Style | null | undefined, fallback: number): number {
  const weight = style?.weight;

  return weight && Object.hasOwn(WEIGHT_PX, weight) ? (WEIGHT_PX[weight] ?? fallback) : fallback;
}

/** The dash a style asks for, or the default's when it says nothing. `double` is two solid lines. */
function dashOf(stroke: StrokeStyle | undefined, fallback: string | undefined): string | undefined {
  switch (stroke) {
    case undefined:
      return fallback;
    case 'dashed':
      return DASHED;
    case 'dotted':
      return DOTTED;
    default:
      return undefined;
  }
}

function drawable(shape: Shape): DrawableShape {
  return shape.kind === 'point' ? { kind: 'circle', at: shape.at, r: PIN_R } : shape;
}

/** A placement that draws nothing of its own: findable, and outlined while "show places" is on. */
function hitOnly(shape: Shape, ctx: ThemeContext): Mark[] {
  const target = drawable(shape);
  const marks: Mark[] = [{ type: 'draw', purpose: 'hit', shape: target, cls: 'm-hit', hit: true }];

  if (ctx.showPlaces) {
    marks.push({
      type: 'draw',
      purpose: 'outline',
      shape: target,
      cls: 'm-outline',
      width: HAIRLINE,
    });
  }

  return marks;
}

type Look = { cls: string; width: number; dash?: string };

function withRound(cls: string, dash: string | undefined): string {
  return dash === DOTTED ? `${cls} m-round` : cls;
}

/** A line (or the edge of nothing): one stroke, or two for `double`. */
function lineMarks(shape: DrawableShape, style: Style | null | undefined, look: Look): Mark[] {
  const width = weightOf(style, look.width);
  const dash = dashOf(style?.stroke, look.dash);

  if (style?.stroke === 'double') {
    return [
      { type: 'draw', purpose: 'line', shape, cls: look.cls, width: width * 3, hit: true },
      { type: 'draw', purpose: 'gap', shape, cls: 'm-gap', width },
    ];
  }

  const mark: DrawMark = {
    type: 'draw',
    purpose: 'line',
    shape,
    cls: withRound(look.cls, dash),
    width,
    hit: true,
  };

  if (dash) mark.dash = dash;

  return [mark];
}

/** An area: a fill and an outline in one element, or a fill and two edges for `double`. */
function areaMarks(shape: DrawableShape, style: Style | null | undefined, look: Look): Mark[] {
  const width = weightOf(style, look.width);
  const dash = dashOf(style?.stroke, look.dash);

  if (style?.stroke === 'double') {
    return [
      { type: 'draw', purpose: 'area', shape, cls: `${look.cls} m-nostroke`, hit: true },
      { type: 'draw', purpose: 'edge', shape, cls: 'm-edge', width: width * 3 },
      { type: 'draw', purpose: 'gap', shape, cls: 'm-gap', width },
    ];
  }

  const mark: DrawMark = {
    type: 'draw',
    purpose: 'area',
    shape,
    cls: withRound(look.cls, dash),
    width,
    hit: true,
  };

  if (dash) mark.dash = dash;

  return [mark];
}

const LINE_NEUTRAL: Look = { cls: 'm-line', width: WEIGHT_PX.thin };
const LINE_ROUTE: Look = { cls: 'm-road-l', width: WEIGHT_PX.thick, dash: DOTTED };
const AREA_NEUTRAL: Look = { cls: 'm-region m-neutral', width: WEIGHT_PX.regular, dash: DASHED };
const AREA_TOWN: Look = { cls: 'm-region m-town', width: WEIGHT_PX.regular, dash: DASHED };
const AREA_WOOD: Look = { cls: 'm-region m-wood', width: WEIGHT_PX.regular, dash: DASHED };
const AREA_WATER: Look = { cls: 'm-water', width: WEIGHT_PX.regular };

function waterLine(shape: DrawableShape, style: Style | null | undefined, ctx: ThemeContext) {
  // A band is a width in the map, not a stroke: the weight scales it and a pattern does not apply.
  const factor = style?.weight ? weightOf(style, WEIGHT_PX.regular) / WEIGHT_PX.regular : 1;

  return [
    {
      type: 'draw',
      purpose: 'band-border',
      shape,
      cls: 'm-river-b',
      width: BAND_BORDER * ctx.design * factor,
    },
    {
      type: 'draw',
      purpose: 'band',
      shape,
      cls: 'm-river',
      width: BAND * ctx.design * factor,
      hit: true,
    },
  ] satisfies Mark[];
}

function reliefMarks(input: MarkInput, shape: DrawableShape): Mark[] {
  const { placement, part, partIndex, ctx } = input;
  const style = placement.style;
  const arcs = reliefArcs(part, `${placement.entry.id}:${partIndex}`, ctx.designUnit);

  if (arcs.length === 0) return areaMarks(shape, style, AREA_NEUTRAL);

  const width = weightOf(style, WEIGHT_PX.regular);
  const dash = dashOf(style?.stroke, '2 6');
  const marks: Mark[] = [{ type: 'draw', purpose: 'hit', shape, cls: 'm-hit', hit: true }];

  arcs.forEach((arc, i) => {
    const mark: DrawMark = {
      type: 'draw',
      purpose: `arc-${i}`,
      shape: ctx.cubic(arc[0], arc[1], arc[2], arc[3]),
      cls: 'm-hill',
      width,
    };

    if (dash) mark.dash = dash;

    marks.push(mark);
  });

  return marks;
}

function pinMarks(input: MarkInput, at: Extract<Shape, { kind: 'point' }>['at']): Mark[] {
  const { placement, ctx } = input;
  const disc: DrawableShape = { kind: 'circle', at, r: PIN_R };

  if (placement.style?.stroke === 'none') return hitOnly(disc, ctx);

  const marks: Mark[] = [
    { type: 'draw', purpose: 'pin', shape: disc, cls: 'm-pinbg', hit: true },
    {
      type: 'icon',
      purpose: 'icon',
      cls: 'm-ico',
      at,
      size: ICON_SIZE,
      icon: iconForKinds(placement.entry.kinds),
    },
  ];

  if (ctx.names && placement.entry.name !== '') {
    marks.push({
      type: 'text',
      purpose: 'label',
      cls: 'm-lbl',
      at: [at[0] + PIN_R + LABEL_GAP, at[1] + LABEL_BASELINE],
      text: placement.entry.name,
    });
  }

  return marks;
}

function peopleMarks(input: MarkInput, at: Extract<Shape, { kind: 'point' }>['at']): Mark[] {
  const { placement, ctx } = input;
  const disc: DrawableShape = { kind: 'circle', at, r: PEOPLE_R };

  if (placement.style?.stroke === 'none') return hitOnly(disc, ctx);

  const marks: Mark[] = [{ type: 'draw', purpose: 'person', shape: disc, cls: 'm-ppl', hit: true }];
  const text = initials(placement.entry.name);

  if (text !== '') {
    marks.push({
      type: 'text',
      purpose: 'initials',
      cls: 'm-ppl-t',
      at: [at[0], at[1] + INITIALS_BASELINE],
      text,
      anchor: 'middle',
    });
  }

  return marks;
}

function areaLook(role: Role | null): Look {
  switch (role) {
    case 'built-up':
    case 'territory':
      return AREA_TOWN;
    case 'vegetation':
      return AREA_WOOD;
    case 'water':
      return AREA_WATER;
    default:
      return AREA_NEUTRAL;
  }
}

/** Areas and water at the bottom, then other lines, then pins; people are above them all. */
function partLayer(part: Part, role: Role | null): number {
  switch (part.shape) {
    case 'point':
      return 2;
    case 'polyline':
      return role === 'water' ? 0 : 1;
    case 'bezier':
      return part.closed || role === 'water' ? 0 : 1;
    default:
      return 0;
  }
}

export const defaultTheme: Theme = {
  name: 'default',
  sheetClass: 'm-land',

  layer(placement: Placement, role: Role | null): number {
    const parts = placement.geometry.parts;

    if (parts.length === 0) return 0;

    if (role === 'presence' && parts.every((part) => part.shape === 'point')) return 3;

    // The lowest layer any part belongs to: a placement is drawn as one.
    return Math.min(...parts.map((part) => partLayer(part, role)));
  },

  marks(input: MarkInput): Mark[] {
    const { role, shape, placement, ctx } = input;
    const style = placement.style;

    if (shape.kind === 'point') {
      return role === 'presence' ? peopleMarks(input, shape.at) : pinMarks(input, shape.at);
    }

    if (style?.stroke === 'none') return hitOnly(shape, ctx);

    if (shape.kind === 'line') {
      if (role === 'water') return waterLine(shape, style, ctx);

      return lineMarks(shape, style, role === 'route' ? LINE_ROUTE : LINE_NEUTRAL);
    }

    if (role === 'relief') return reliefMarks(input, shape);

    return areaMarks(shape, style, areaLook(role));
  },
};
