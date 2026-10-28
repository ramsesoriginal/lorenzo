import type { DrawableShape, Mark, MarkInput, Shape, Theme } from '../theme';
import type { Placement, Role, Style } from '../types';
import {
  areaMarks,
  defaultTheme,
  hitOnly,
  INITIALS_BASELINE,
  initials,
  LABEL_BASELINE,
  LABEL_GAP,
  type Look,
  lineMarks,
  PEOPLE_RADIUS,
  WEIGHT_PX,
} from './default';

/**
 * The plain theme (ADR 0352): a black-and-white schematic. No fills, no relief arcs and no icons:
 * an area is an outline, a line a stroke, a place a dot with its name and a person a ring with its
 * initials. One role is told from another by pattern only (water double, routes dashed, boundaries
 * dotted), and the same classes as the default theme carry the states; the stylesheet restyles
 * them under `data-theme="plain"`.
 */

const DOT_R = 5;
const DOT_HIT_R = 12;

/** The pattern a role is drawn with when the placement's own style says nothing. */
const ROLE_STROKE: Readonly<Partial<Record<Role, NonNullable<Style['stroke']>>>> = {
  water: 'double',
  route: 'dashed',
  conduit: 'dashed',
  passage: 'dashed',
  territory: 'dashed',
  boundary: 'dotted',
  barrier: 'dotted',
  hazard: 'dotted',
};

const LINE: Look = { cls: 'm-line', width: WEIGHT_PX.thin };
const AREA: Look = { cls: 'm-region m-neutral', width: WEIGHT_PX.thin };

/** The placement's style with the role's pattern under it. */
function styleOf(placement: Placement, role: Role | null): Style | null {
  const fallback = role ? ROLE_STROKE[role] : undefined;
  const own = placement.style ?? null;

  if (!fallback) return own;

  return { stroke: fallback, ...(own ?? {}) };
}

function dotMarks(input: MarkInput, at: Extract<Shape, { kind: 'point' }>['at']): Mark[] {
  const { placement, ctx } = input;
  const disc: DrawableShape = { kind: 'circle', at, r: DOT_HIT_R };

  if (placement.style?.stroke === 'none') return hitOnly(disc, ctx);

  const marks: Mark[] = [
    { type: 'draw', purpose: 'hit', shape: disc, cls: 'm-hit', hit: true },
    {
      type: 'draw',
      purpose: 'pin',
      shape: { kind: 'circle', at, r: DOT_R },
      cls: 'm-pinbg',
      hit: true,
    },
  ];

  if (ctx.names && placement.entry.name !== '') {
    marks.push({
      type: 'text',
      purpose: 'label',
      cls: 'm-lbl',
      at: [at[0] + DOT_R + LABEL_GAP, at[1] + LABEL_BASELINE],
      text: placement.entry.name,
    });
  }

  return marks;
}

function ringMarks(input: MarkInput, at: Extract<Shape, { kind: 'point' }>['at']): Mark[] {
  const { placement, ctx } = input;
  const disc: DrawableShape = { kind: 'circle', at, r: PEOPLE_RADIUS };

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

export const plainTheme: Theme = {
  name: 'plain',
  sheetClass: 'm-land',

  layer: defaultTheme.layer,

  marks(input: MarkInput): Mark[] {
    const { role, shape, placement, ctx } = input;

    if (shape.kind === 'point') {
      return role === 'presence' ? ringMarks(input, shape.at) : dotMarks(input, shape.at);
    }

    if (placement.style?.stroke === 'none') return hitOnly(shape, ctx);

    const style = styleOf(placement, role);

    return shape.kind === 'line' ? lineMarks(shape, style, LINE) : areaMarks(shape, style, AREA);
  },
};
