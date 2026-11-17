import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
  defaultTheme,
  HANDLE_PICK,
  handleAt,
  layout,
  legend,
  OVERLAY_TONES,
  type Overlay,
  overlayPrims,
  type PathPrim,
  plainTheme,
  ROLES,
  SWATCH,
  sceneToSvg,
  THEME_NAMES,
  themeNamed,
  themes,
} from '../src';
import { transformOf } from '../src/project';
import { mara, model, river, road, shrine, system, town, view } from './fixtures';

describe('themes', () => {
  it('names the themes the API knows, and an unknown name is the default', () => {
    const golden = JSON.parse(
      readFileSync(new URL('../../map-engine/golden/themes.json', import.meta.url), 'utf8'),
    ) as { names: string[] };

    expect([...THEME_NAMES]).toEqual(golden.names);
    expect(Object.keys(themes)).toEqual(golden.names);
    expect(themeNamed('plain')).toBe(plainTheme);
    expect(themeNamed('default')).toBe(defaultTheme);
    for (const name of [null, undefined, '', 'tube', 'toString', '__proto__']) {
      expect(themeNamed(name)).toBe(defaultTheme);
    }
  });

  it('draws the same Map in the plain theme with no icon, fill or relief arcs', () => {
    const scene = layout(model, view(), plainTheme);
    const text = JSON.stringify(scene);

    expect(scene.theme).toBe('plain');
    expect(scene.prims.some((p) => p.kind === 'icon')).toBe(false);
    expect(text).not.toContain('m-hill');
    expect(text).not.toContain('m-town');
    // Every placement is still in it, and reachable.
    const entries = new Set(scene.prims.flatMap((p) => (p.entryId ? [p.entryId] : [])));

    expect(entries).toEqual(new Set(model.placements.map((p) => p.entry.id)));
    for (const entry of entries) {
      expect(scene.prims.find((p) => p.entryId === entry)?.label).toBeTruthy();
    }
  });

  it('tells a role by pattern: water double, a route dashed, and a style overrides it', () => {
    const lines = (placement: typeof river) =>
      layout({ system, placements: [placement] }, view(), plainTheme).prims.filter(
        (p): p is PathPrim => p.kind === 'path',
      );

    expect(lines(river).map((p) => p.cls)).toEqual(['m-line', 'm-gap']);
    expect(lines(road)[0]?.dash).toBe('6 5');
    const solid = { ...road, style: { stroke: 'solid' as const } };

    expect(lines(solid)[0]?.dash).toBeUndefined();
  });

  it('keeps hit-only placements findable, as the default does', () => {
    const none = { ...town, style: { stroke: 'none' as const } };
    const scene = layout({ system, placements: [none] }, view(), plainTheme);

    expect(scene.prims.some((p) => p.cls === 'm-hit' && p.hit)).toBe(true);
  });
});

describe('legend', () => {
  it('lists each role on the Map once, in the order of the closed list, with a swatch of the theme', () => {
    const items = legend(model, defaultTheme);
    const present = new Set(model.placements.map((p) => p.role ?? 'none'));
    const expected = [
      ...ROLES.filter((r) => present.has(r)),
      ...(present.has('none') ? ['none'] : []),
    ];

    expect(items.map((i) => i.key)).toEqual(expected);
    expect(items.find((i) => i.key === 'built-up')?.label).toBe('Built-up area');
    for (const item of items) {
      expect(item.swatch.width).toBe(SWATCH.width);
      expect(item.swatch.height).toBe(SWATCH.height);
      expect(item.swatch.prims.length).toBeGreaterThan(1);
    }
  });

  it('draws each swatch with the theme it was asked for, and reads no name', () => {
    const plain = legend(model, plainTheme);
    const text = JSON.stringify(plain);

    expect(plain.every((i) => i.swatch.theme === 'plain')).toBe(true);
    for (const placement of model.placements) {
      expect(text).not.toContain(placement.entry.name);
    }
    expect(JSON.stringify(legend(model, defaultTheme))).toContain('icon');
  });

  it('shows the kind of shape each role is drawn as on this Map, and a lake for water', () => {
    const items = legend(model, defaultTheme);
    const cls = (key: string) =>
      items.find((i) => i.key === key)?.swatch.prims.map((p) => p.cls) ?? [];

    expect(cls('route').some((c) => c.includes('m-road-l'))).toBe(true);
    expect(cls('water')).toContain('m-water');
    expect(cls('presence').some((c) => c.includes('m-ppl'))).toBe(true);
  });

  it('has nothing for a Map with nothing drawn, and a line for placements with no role', () => {
    expect(legend({ system, placements: [] })).toEqual([]);
    expect(legend({ system, placements: [{ ...shrine, role: null }] }).map((i) => i.key)).toEqual([
      'none',
    ]);
    expect(legend({ system, placements: [{ ...mara, role: 'dragon' }] }).map((i) => i.key)).toEqual(
      ['none'],
    );
  });
});

describe('the overlay an editor draws', () => {
  const overlay: Overlay = [
    {
      id: 'draft',
      kind: 'line',
      pts: [
        [0, 0],
        [100, 0],
        [100, 100],
      ],
      closed: true,
    },
    {
      id: 'band',
      kind: 'line',
      pts: [
        [100, 100],
        [50, 50],
      ],
      preview: true,
    },
    { id: 'ring', kind: 'disc', at: [200, 200], r: 20 },
    { id: 'p0', kind: 'handle', at: [0, 0] },
    { id: 'p1', kind: 'handle', at: [100, 0], active: true },
  ];

  it('is drawn after the marks, as primitives that take no pointer', () => {
    const plain = layout(model, view());
    const scene = layout(model, view({ overlay }));
    const extra = scene.prims.slice(plain.prims.length);

    expect(scene.prims.slice(0, plain.prims.length)).toEqual(plain.prims);
    expect(extra.map((p) => p.id)).toEqual([
      'overlay:draft',
      'overlay:band',
      'overlay:ring',
      'overlay:p0',
      'overlay:p1',
    ]);
    expect(extra.every((p) => p.cls.startsWith('m-ov') && !p.entryId && !p.hit)).toBe(true);
    expect(extra[1]?.cls).toContain('m-ov-preview');
    expect(extra[4]?.cls).toContain('m-ov-active');
    expect((extra[0] as PathPrim).d.endsWith(' Z')).toBe(true);
  });

  describe('a filled area and a divider (ADR 0475)', () => {
    const square: [number, number][] = [
      [100, 100],
      [300, 100],
      [300, 300],
      [100, 300],
    ];
    const hole: [number, number][] = [
      [150, 150],
      [250, 150],
      [250, 250],
    ];
    const preview: Overlay = [
      { id: 'cave', kind: 'area', rings: [square, hole], clipped: true },
      {
        id: 'contour',
        kind: 'line',
        pts: [
          [0, 0],
          [100, 0],
        ],
        clipped: true,
      },
      { id: 'p0', kind: 'handle', at: [0, 0] },
    ];

    it('draws an area as one even-odd path, its holes cut out, that takes no pointer', () => {
      const scene = layout(model, view({ overlay: preview }));
      const area = scene.prims.find((p) => p.id === 'overlay:cave') as PathPrim;

      expect(area.cls).toBe('m-ov m-ov-area');
      expect(area.fillRule).toBe('evenodd');
      expect(area.d).toBe(
        'M 100 100 L 300 100 L 300 300 L 100 300 Z M 150 150 L 250 150 L 250 250 Z',
      );
      expect(area.bbox).toEqual([100, 100, 300, 300]);
      expect(area.entryId).toBeUndefined();
      expect(area.hit).toBeUndefined();
      // With no divider nothing is clipped and no divider is drawn.
      expect(area.clip).toBeUndefined();
      expect(scene.prims.some((p) => p.id === 'overlay:divider')).toBe(false);
    });

    it('draws an area in one of six tones when it is given one', () => {
      const toned = (tone: number) =>
        layout(
          model,
          view({ overlay: [{ id: 't', kind: 'area', rings: [square], tone }] }),
        ).prims.find((p) => p.id === 'overlay:t')?.cls;

      expect(OVERLAY_TONES).toBe(6);
      expect(toned(0)).toBe('m-ov m-ov-area m-ov-tone-0');
      expect(toned(5)).toBe('m-ov m-ov-area m-ov-tone-5');
      // A tone beyond the six is the nearest of them, and a part of one is the whole below it.
      expect(toned(9)).toBe('m-ov m-ov-area m-ov-tone-5');
      expect(toned(-2)).toBe('m-ov m-ov-area m-ov-tone-0');
      expect(toned(2.7)).toBe('m-ov m-ov-area m-ov-tone-2');
    });

    it('with a divider draws the clipped shapes to its right only, and the divider itself', () => {
      const scene = layout(model, view({ overlay: preview, overlayDivide: 0.25 }));
      const byId = (id: string) => scene.prims.find((p) => p.id === id);

      // The view is 1000 by 640: a quarter of the way across is 250.
      expect(byId('overlay:cave')?.clip).toEqual([250, 0, 1000, 640]);
      expect(byId('overlay:contour')?.clip).toEqual([250, 0, 1000, 640]);
      expect(byId('overlay:p0')?.clip).toBeUndefined();
      expect(byId('overlay:divider')).toMatchObject({
        kind: 'path',
        cls: 'm-ov m-ov-divider',
        d: 'M 250 0 L 250 640',
      });
      expect(scene.prims[scene.prims.length - 1]?.id).toBe('overlay:divider');
      // A divider beyond the view stays at its edge.
      expect(
        layout(model, view({ overlay: preview, overlayDivide: 7 })).prims.find(
          (p) => p.id === 'overlay:divider',
        ),
      ).toMatchObject({ d: 'M 1000 0 L 1000 640' });
      // An overlay with nothing clipped has no divider, wherever the view is split.
      expect(
        layout(
          model,
          view({ overlay: [{ id: 'p0', kind: 'handle', at: [0, 0] }], overlayDivide: 0.5 }),
        ).prims.some((p) => p.id === 'overlay:divider'),
      ).toBe(false);
    });

    it('is painted with one clip for the shapes that share it', () => {
      const svg = sceneToSvg(layout(model, view({ overlay: preview, overlayDivide: 0.25 })), {
        idPrefix: 'm',
      });

      expect(svg.match(/<clipPath /g)).toHaveLength(1);
      expect(svg).toContain('<clipPath id="m-clip-0"><rect x="250" y="0" width="750" height="640"');
      expect(svg.match(/clip-path="url\(#m-clip-0\)"/g)).toHaveLength(2);
      expect(sceneToSvg(layout(model, view({ overlay: preview })))).not.toContain('clipPath');
    });
  });

  it('puts handles where the drawing point is on the screen, and a disc by drawing units', () => {
    const v = view({ overlay });
    const t = transformOf(system, v);
    const prims = overlayPrims(overlay, system, t);
    const handle = prims.find((p) => p.id === 'overlay:p1');
    const ring = prims.find((p) => p.id === 'overlay:ring');

    expect(handle && 'cx' in handle ? [handle.cx, handle.cy] : null).toEqual([
      Math.round(((100 - t.centre[0]) * t.scale + t.width / 2) * 100) / 100,
      Math.round(((0 - t.centre[1]) * t.scale + t.height / 2) * 100) / 100,
    ]);
    expect(ring && 'r' in ring ? ring.r : 0).toBeCloseTo(20 * t.scale, 1);
  });

  it('picks the nearest handle within reach, and none beyond it', () => {
    const t = transformOf(system, view({ overlay }));
    const at = (x: number, y: number): [number, number] => [
      (x - t.centre[0]) * t.scale + t.width / 2,
      (y - t.centre[1]) * t.scale + t.height / 2,
    ];
    const near = at(100, 0);

    expect(handleAt(overlay, system, t, [near[0] + 3, near[1] - 2])).toBe('p1');
    expect(handleAt(overlay, system, t, at(0, 0))).toBe('p0');
    expect(handleAt(overlay, system, t, [near[0] + HANDLE_PICK + 5, near[1]])).toBeNull();
    expect(handleAt([], system, t, near)).toBeNull();
  });

  it('is nothing when there is no overlay', () => {
    expect(layout(model, view({ overlay: [] }))).toEqual(layout(model, view()));
  });
});
