import { layout } from './layout';
import type { Scene } from './scene';
import type { Theme } from './theme';
import { defaultTheme } from './themes/default';
import {
  DEFAULT_GROUPS,
  type Geometry,
  type MapModel,
  normaliseRole,
  type Part,
  type Placement,
  ROLE_WORDS,
  ROLES,
  type Role,
} from './types';

/**
 * The legend of a Map (ADR 0352): what each role present on it looks like in a theme. Furniture,
 * not data: it reads each placement's role and the kind of its first part and nothing else, so no
 * name or entry can reach it, and the theme draws every swatch itself.
 */

/** A swatch's size in screen pixels. */
export const SWATCH = { width: 44, height: 34 } as const;

export type LegendItem = {
  /** The role, or `"none"` for placements with no role (or one this version does not know). */
  key: Role | 'none';
  /** In words, capitalised: "Built-up area". */
  label: string;
  /** Draw it with `paintSvg` into an `<svg>` of `SWATCH` size. */
  swatch: Scene;
};

type Kind = 'point' | 'line' | 'area';

function kindOf(part: Part | undefined): Kind {
  switch (part?.shape) {
    case 'polyline':
      return 'line';
    case 'bezier':
      return part.closed ? 'area' : 'line';
    case 'circle':
    case 'polygon':
      return 'area';
    default:
      return 'point';
  }
}

function sample(kind: Kind): Geometry {
  const { width: w, height: h } = SWATCH;

  switch (kind) {
    case 'line':
      return {
        format: 'lorenzo.geometry/1',
        parts: [
          {
            shape: 'polyline',
            pts: [
              [4, h - 8],
              [w / 2, 8],
              [w - 4, h - 8],
            ],
          },
        ],
      };
    case 'area':
      return {
        format: 'lorenzo.geometry/1',
        parts: [
          {
            shape: 'polygon',
            rings: [
              [
                [5, 6],
                [w - 5, 6],
                [w - 5, h - 6],
                [5, h - 6],
              ],
            ],
          },
        ],
      };
    default:
      return {
        format: 'lorenzo.geometry/1',
        parts: [{ shape: 'point', at: [w / 2, h / 2] }],
      };
  }
}

function labelOf(key: Role | 'none'): string {
  if (key === 'none') return 'Other places';

  const words = ROLE_WORDS[key];

  return words.charAt(0).toUpperCase() + words.slice(1);
}

/**
 * One item for each role that appears in `model`, in the order of the closed list, and one for
 * placements with no role last. A Map with nothing drawn has no legend.
 */
export function legend(
  model: MapModel,
  theme: Theme = defaultTheme,
  options: { iconBase?: string } = {},
): LegendItem[] {
  const first = new Map<Role | 'none', Placement>();

  for (const placement of model.placements) {
    const key = normaliseRole(placement.role) ?? 'none';

    if (!first.has(key)) first.set(key, placement);
  }

  const keys: (Role | 'none')[] = [...ROLES.filter((role) => first.has(role))];

  if (first.has('none')) keys.push('none');

  return keys.map((key) => {
    const from = first.get(key);
    const role = key === 'none' ? null : key;
    // Water is shown as a lake: a river's band is measured against the width of its sheet.
    const kind = role === 'water' ? 'area' : kindOf(from?.geometry.parts[0]);
    const swatch = layout(
      {
        system: { kind: 'plane', extent: [0, 0, SWATCH.width, SWATCH.height] },
        placements: [
          {
            entry: {
              id: `legend-${key}`,
              name: role === 'presence' ? 'A B' : '',
              kinds: from?.entry.kinds ?? [],
            },
            geometry: sample(kind),
            role,
            z: 0,
          },
        ],
      },
      {
        viewport: { width: SWATCH.width, height: SWATCH.height },
        zoom: 1,
        centre: [SWATCH.width / 2, SWATCH.height / 2],
        groups: { ...DEFAULT_GROUPS, names: false },
        selection: null,
        ...(options.iconBase === undefined ? {} : { iconBase: options.iconBase }),
      },
      theme,
    );

    return { key, label: labelOf(key), swatch };
  });
}
