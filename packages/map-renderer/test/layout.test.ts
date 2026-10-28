import { describe, expect, it } from 'vitest';
import {
  type CirclePrim,
  DEFAULT_GROUPS,
  layout,
  type MapModel,
  normaliseRole,
  type PathPrim,
  type Prim,
  type Scene,
  type Style,
  type TextPrim,
} from '../src';
import { mara, model, place, river, road, shrine, stag, system, town, view } from './fixtures';

function byId(scene: Scene, id: string): Prim {
  const prim = scene.prims.find((p) => p.id === id);

  if (!prim) throw new Error(`no primitive ${id} in ${scene.prims.map((p) => p.id).join(', ')}`);

  return prim;
}

function ids(scene: Scene): string[] {
  return scene.prims.map((p) => p.id);
}

describe('layout', () => {
  it('is deterministic: the same input is the same bytes', () => {
    const a = JSON.stringify(layout(model, view({ selection: 'town', hover: 'stag' })));
    const b = JSON.stringify(
      layout(structuredClone(model), view({ selection: 'town', hover: 'stag' })),
    );

    expect(a).toBe(b);
  });

  it('is plain data that survives a JSON round trip', () => {
    const scene = layout(model, view());

    expect(JSON.parse(JSON.stringify(scene))).toEqual(scene);
  });

  it('rounds every number to two decimals', () => {
    const scene = layout(model, view({ zoom: 1.2345678, centre: [333.3333, 222.2222] }));
    const numbers = JSON.stringify(scene).match(/-?\d+\.\d+/g) ?? [];

    expect(numbers.length).toBeGreaterThan(0);

    for (const n of numbers) expect(n.split('.')[1]?.length).toBeLessThanOrEqual(2);
  });

  describe('rejects what is not finite', () => {
    it.each([
      ['a NaN zoom', view({ zoom: Number.NaN })],
      ['an infinite zoom', view({ zoom: Number.POSITIVE_INFINITY })],
      ['a zero zoom', view({ zoom: 0 })],
      ['a NaN centre', view({ centre: [Number.NaN, 0] })],
      ['an infinite centre', view({ centre: [0, Number.NEGATIVE_INFINITY] })],
      ['an empty viewport', view({ viewport: { width: 0, height: 100 } })],
      ['a NaN viewport', view({ viewport: { width: Number.NaN, height: 100 } })],
    ])('%s', (_name, v) => {
      expect(() => layout(model, v)).toThrow(RangeError);
    });

    it('a NaN coordinate in a placement', () => {
      const bad: MapModel = {
        system,
        placements: [place('x', 'X', [], [{ shape: 'point', at: [Number.NaN, 4] }])],
      };

      expect(() => layout(bad, view())).toThrow(RangeError);
    });

    it('an infinite control point and a NaN radius', () => {
      const bezier: MapModel = {
        system,
        placements: [
          place(
            'x',
            'X',
            [],
            [
              {
                shape: 'bezier',
                start: [0, 0],
                segs: [
                  [
                    [1, 1],
                    [Number.POSITIVE_INFINITY, 2],
                    [3, 3],
                  ],
                ],
              },
            ],
          ),
        ],
      };
      const circle: MapModel = {
        system,
        placements: [place('x', 'X', [], [{ shape: 'circle', at: [1, 1], r: Number.NaN }])],
      };

      expect(() => layout(bezier, view())).toThrow(RangeError);
      expect(() => layout(circle, view())).toThrow(RangeError);
    });

    it('an extent without area', () => {
      const flat = { ...model, system: { ...system, extent: [0, 0, 0, 10] as const } };

      expect(() => layout(flat, view())).toThrow(RangeError);
    });
  });

  describe('what each shape and role is drawn as', () => {
    const scene = layout(model, view());

    it('draws the sheet first, as a rect over the whole viewport', () => {
      expect(scene.prims[0]).toEqual({
        id: 'sheet',
        kind: 'rect',
        cls: 'm-land',
        x: 0,
        y: 0,
        width: 1000,
        height: 640,
        bbox: [0, 0, 1000, 640],
      });
    });

    it('draws water as a line as a bordered band', () => {
      const border = byId(scene, 'river:0:band-border') as PathPrim;
      const band = byId(scene, 'river:0:band') as PathPrim;

      expect(border.cls).toBe('m-river-b');
      expect(band.cls).toBe('m-river');
      expect(border.strokeWidth).toBe(46);
      expect(band.strokeWidth).toBe(40);
      expect(band.d).toBe('M 690 -120 L 730 60 L 790 270 L 720 640');
      expect(band.hit).toEqual({ mode: 'line', tol: 20 });
      expect(border.hit).toBeUndefined();
    });

    it('draws built-up as a dashed outline and a warm fill, with the hole cut out', () => {
      const area = byId(scene, 'town:0:area') as PathPrim;

      expect(area.cls).toBe('m-region m-town');
      expect(area.dash).toBe('6 5');
      expect(area.strokeWidth).toBe(2);
      expect(area.fillRule).toBe('evenodd');
      expect(area.d).toBe(
        'M 300 200 L 700 200 L 700 500 L 300 500 Z M 450 300 L 550 300 L 550 400 L 450 400 Z',
      );
      expect(area.hit).toEqual({ mode: 'area' });
    });

    it('draws territory like built-up and vegetation with the success fill', () => {
      const parts = town.geometry.parts;
      const s = layout(
        {
          system,
          placements: [
            place('t', 'T', [], parts, { role: 'territory' }),
            place('v', 'V', [], parts, { role: 'vegetation' }),
          ],
        },
        view(),
      );

      expect((byId(s, 't:0:area') as PathPrim).cls).toBe('m-region m-town');
      expect((byId(s, 'v:0:area') as PathPrim).cls).toBe('m-region m-wood');
    });

    it('draws water as an area filled in the water colours', () => {
      const s = layout(
        {
          system,
          placements: [
            place('lake', 'Lake', [], [{ shape: 'circle', at: [200, 200], r: 50 }], {
              role: 'water',
            }),
          ],
        },
        view(),
      );
      const lake = byId(s, 'lake:0:area') as CirclePrim;

      expect(lake.kind).toBe('circle');
      expect(lake.cls).toBe('m-water');
      expect(lake.r).toBe(50);
    });

    it('draws a route dotted, round and 3 wide', () => {
      const line = byId(scene, 'road:0:line') as PathPrim;

      expect(line.cls).toBe('m-road-l m-round');
      expect(line.dash).toBe('1 7');
      expect(line.strokeWidth).toBe(3);
      expect(line.d).toBe('M 100 100 L 400 300');
    });

    it('draws a point of any role as a disc with its icon and its name', () => {
      const disc = byId(scene, 'stag:0:pin') as CirclePrim;
      const icon = byId(scene, 'stag:0:icon');
      const label = byId(scene, 'stag:0:label') as TextPrim;

      expect([disc.cx, disc.cy, disc.r, disc.cls]).toEqual([400, 300, 15, 'm-pinbg']);
      expect(icon).toMatchObject({ kind: 'icon', icon: 'kind-location', x: 390, y: 290, size: 20 });
      expect(label).toMatchObject({ kind: 'text', text: 'The Gilded Stag', x: 418, y: 304.5 });
    });

    it('takes the icon of the first kind it knows, a place otherwise', () => {
      const s = layout(
        {
          system,
          placements: [
            place('a', 'A', ['unheard-of', 'item'], [{ shape: 'point', at: [1, 1] }]),
            place('b', 'B', ['unheard-of'], [{ shape: 'point', at: [2, 2] }], { role: 'site' }),
          ],
        },
        view(),
      );

      expect(byId(s, 'a:0:icon')).toMatchObject({ icon: 'kind-item' });
      expect(byId(s, 'b:0:icon')).toMatchObject({ icon: 'kind-location' });
    });

    it('draws presence as a 12 disc of initials', () => {
      const disc = byId(scene, 'mara:0:person') as CirclePrim;
      const text = byId(scene, 'mara:0:initials') as TextPrim;

      expect([disc.cx, disc.cy, disc.r, disc.cls]).toEqual([410, 330, 12, 'm-ppl']);
      expect(text).toMatchObject({ text: 'MQ', anchor: 'middle', x: 410, y: 333.75 });
    });

    it('draws a role it does not know, and none, as the neutral mark of the geometry', () => {
      const parts = town.geometry.parts;
      const line = road.geometry.parts;
      const s = layout(
        {
          system,
          placements: [
            place('a', 'A', [], parts, { role: 'no-such-role' }),
            place('b', 'B', [], parts),
            place('c', 'C', [], line, { role: 'boundary' }),
            place('d', 'D', [], line, { role: 'no-such-role' }),
          ],
        },
        view(),
      );

      for (const id of ['a', 'b']) {
        const p = byId(s, `${id}:0:area`) as PathPrim;

        expect(p.cls).toBe('m-region m-neutral');
        expect(p.dash).toBe('6 5');
      }

      for (const id of ['c', 'd']) {
        const p = byId(s, `${id}:0:line`) as PathPrim;

        expect(p.cls).toBe('m-line');
        expect(p.strokeWidth).toBe(1.5);
        expect(p.dash).toBeUndefined();
      }

      expect(normaliseRole('no-such-role')).toBeNull();
      expect(normaliseRole(null)).toBeNull();
      expect(normaliseRole('route')).toBe('route');
    });

    it('draws an open bezier as a line and a closed one as an area', () => {
      const segs = [
        [
          [10, 0],
          [20, 10],
          [30, 0],
        ],
      ] as const;
      const s = layout(
        {
          system,
          placements: [
            place('o', 'O', [], [{ shape: 'bezier', start: [0, 0], segs }]),
            place('c', 'C', [], [{ shape: 'bezier', start: [0, 0], segs, closed: true }]),
          ],
        },
        view(),
      );

      expect((byId(s, 'o:0:line') as PathPrim).d).toBe('M 0 0 C 10 0 20 10 30 0');
      expect((byId(s, 'c:0:area') as PathPrim).d).toBe('M 0 0 C 10 0 20 10 30 0 Z');
    });

    it('draws a circle part as a circle in drawing units', () => {
      const s = layout(
        {
          system,
          placements: [
            place('c', 'C', [], [{ shape: 'circle', at: [500, 320], r: 100 }], {
              role: 'territory',
            }),
          ],
        },
        view({ zoom: 2 }),
      );
      const c = byId(s, 'c:0:area') as CirclePrim;

      expect([c.cx, c.cy, c.r]).toEqual([500, 320, 200]);
    });

    it('skips a part with too little to draw, and a shape it does not know', () => {
      const s = layout(
        {
          system,
          placements: [
            place('a', 'A', [], [{ shape: 'polyline', pts: [[1, 1]] }]),
            place('b', 'B', [], [{ shape: 'circle', at: [1, 1], r: 0 }]),
            place(
              'c',
              'C',
              [],
              [
                {
                  shape: 'polygon',
                  rings: [
                    [
                      [1, 1],
                      [2, 2],
                    ],
                  ],
                },
              ],
            ),
            place('d', 'D', [], [{ shape: 'sphere' } as never]),
          ],
        },
        view(),
      );

      expect(ids(s)).toEqual(['sheet']);
    });
  });

  describe('relief', () => {
    const hills = place(
      'hills',
      'The Hills',
      [],
      [
        {
          shape: 'polygon',
          rings: [
            [
              [100, 400],
              [500, 400],
              [500, 620],
              [100, 620],
            ],
          ],
        },
      ],
      { role: 'relief' },
    );
    const sameShape = place('ridge', 'Ridge', [], hills.geometry.parts, { role: 'relief' });
    const arcsOf = (s: Scene, id: string) =>
      s.prims.filter((p) => p.id.startsWith(`${id}:0:arc-`)) as PathPrim[];

    it('is a row of dotted arcs, round capped, 2 wide, with the area as its hit', () => {
      const s = layout({ system, placements: [hills] }, view());
      const arcs = arcsOf(s, 'hills');

      expect(arcs.length).toBeGreaterThan(1);

      for (const arc of arcs) {
        expect(arc).toMatchObject({ cls: 'm-hill', dash: '2 6', strokeWidth: 2, kind: 'path' });
        expect(arc.hit).toBeUndefined();
        expect(arc.d).toMatch(/^M [-\d. ]+ C [-\d. ]+$/);
      }

      expect(byId(s, 'hills:0:hit')).toMatchObject({ cls: 'm-hit', hit: { mode: 'area' } });
    });

    it('never moves: the same arcs on every call, and zoom only scales them', () => {
      const a = layout({ system, placements: [hills] }, view());
      const b = layout({ system, placements: [hills] }, view());
      const zoomed = layout({ system, placements: [hills] }, view({ zoom: 2 }));

      expect(arcsOf(a, 'hills').map((p) => p.d)).toEqual(arcsOf(b, 'hills').map((p) => p.d));
      expect(arcsOf(zoomed, 'hills')).toHaveLength(arcsOf(a, 'hills').length);
      expect(arcsOf(zoomed, 'hills')[0]?.strokeWidth).toBe(2);
    });

    it('differs between entry ids, on the very same shape', () => {
      const s = layout({ system, placements: [hills, sameShape] }, view());

      expect(arcsOf(s, 'hills').map((p) => p.d)).not.toEqual(arcsOf(s, 'ridge').map((p) => p.d));
    });

    it('falls back to the dashed outline when no arc fits', () => {
      const thin = place(
        'thin',
        'Thin',
        [],
        [
          {
            shape: 'polygon',
            rings: [
              [
                [0, 0],
                [200, 0],
                [200, 2],
                [0, 2],
              ],
            ],
          },
        ],
        { role: 'relief' },
      );
      const s = layout({ system, placements: [thin] }, view());

      expect(byId(s, 'thin:0:area')).toMatchObject({ cls: 'm-region m-neutral' });
    });
  });

  describe('the view', () => {
    it('puts the centre at the middle of the viewport, zoom 1 fitting the sheet', () => {
      const s = layout(model, view());

      expect(byId(s, 'stag:0:pin')).toMatchObject({ cx: 400, cy: 300 });
    });

    it('fits the sheet with a letterbox when the viewport is wider', () => {
      const s = layout(model, view({ viewport: { width: 2000, height: 640 } }));

      // The sheet fits by height (scale 1), centred: its left edge is at x = 500.
      expect(byId(s, 'stag:0:pin')).toMatchObject({ cx: 900, cy: 300 });
      expect(s.width).toBe(2000);
    });

    it('scales positions and map-unit widths with the zoom, and nothing else', () => {
      const one = layout(model, view());
      const two = layout(model, view({ zoom: 2, centre: [300, 200] }));

      // Pin at (400, 300): twice the distance from the centre, at the viewport middle.
      expect(byId(two, 'stag:0:pin')).toMatchObject({ cx: 700, cy: 520, r: 15 });
      expect((byId(two, 'river:0:band') as PathPrim).strokeWidth).toBe(80);
      expect((byId(two, 'river:0:band-border') as PathPrim).strokeWidth).toBe(92);
      expect((byId(two, 'town:0:area') as PathPrim).strokeWidth).toBe(2);
      expect((byId(two, 'road:0:line') as PathPrim).strokeWidth).toBe(3);
      expect(byId(two, 'stag:0:label')).toMatchObject({ x: 718, y: 524.5 });
      expect(byId(two, 'stag:0:icon')).toMatchObject({ size: 20 });
      expect((byId(one, 'river:0:band') as PathPrim).strokeWidth).toBe(40);
    });

    it('measures a river against the sheet, so a bigger sheet has a river as wide on screen', () => {
      const big = { ...system, extent: [0, 0, 100000, 64000] as const };
      const s = layout(
        {
          system: big,
          placements: [
            place(
              'r',
              'R',
              [],
              [
                {
                  shape: 'polyline',
                  pts: [
                    [0, 0],
                    [9, 9],
                  ],
                },
              ],
              { role: 'water' },
            ),
          ],
        },
        view({ centre: [50000, 32000] }),
      );

      expect((byId(s, 'r:0:band') as PathPrim).strokeWidth).toBe(40);
    });

    it('boxes each primitive in screen pixels', () => {
      const s = layout(model, view({ zoom: 2, centre: [300, 200] }));

      expect(byId(s, 'stag:0:pin').bbox).toEqual([685, 505, 715, 535]);
      expect(byId(s, 'stag:0:icon').bbox).toEqual([690, 510, 710, 530]);
    });
  });

  describe('the groups', () => {
    const base = ids(layout(model, view()));

    it('hides Places: everything but presence and route', () => {
      const s = ids(layout(model, view({ groups: { ...DEFAULT_GROUPS, places: false } })));

      expect(s.some((id) => id.startsWith('town:') || id.startsWith('stag:'))).toBe(false);
      expect(s.some((id) => id.startsWith('mara:'))).toBe(true);
      expect(s.some((id) => id.startsWith('road:'))).toBe(true);
    });

    it('hides People: presence only', () => {
      const s = ids(layout(model, view({ groups: { ...DEFAULT_GROUPS, people: false } })));

      expect(s.some((id) => id.startsWith('mara:'))).toBe(false);
      expect(s).toHaveLength(base.length - 2);
    });

    it('hides Roads: route only', () => {
      const s = ids(layout(model, view({ groups: { ...DEFAULT_GROUPS, roads: false } })));

      expect(s.some((id) => id.startsWith('road:'))).toBe(false);
      expect(s).toHaveLength(base.length - 1);
    });

    it('hides Names: the labels and nothing else', () => {
      const s = ids(layout(model, view({ groups: { ...DEFAULT_GROUPS, names: false } })));

      expect(s.filter((id) => id.endsWith(':label'))).toEqual([]);
      expect(base.filter((id) => id.endsWith(':label')).length).toBe(2);
      expect(s).toHaveLength(base.length - 2);
    });

    it('draws an unknown role with the Places group', () => {
      const m = {
        system,
        placements: [place('u', 'U', [], [{ shape: 'point', at: [1, 1] }], { role: 'nonsense' })],
      };

      expect(ids(layout(m, view({ groups: { ...DEFAULT_GROUPS, places: false } })))).toEqual([
        'sheet',
      ]);
      expect(ids(layout(m, view()))).toContain('u:0:pin');
    });
  });

  describe('order', () => {
    it('is the sheet, areas and water, other lines, pins, then people, each by z then entry id', () => {
      const raised = place('aaa', 'Raised', [], town.geometry.parts, { role: 'built-up', z: 5 });
      const lowered = place('zzz', 'Lowered', [], town.geometry.parts, { role: 'built-up', z: -5 });
      const s = layout(
        { system, placements: [raised, mara, stag, lowered, shrine, road, river] },
        view(),
      );
      const order = s.prims
        .map((p) => p.entryId ?? 'sheet')
        .filter((id, i, all) => id !== all[i - 1]);

      expect(order).toEqual(['sheet', 'zzz', 'river', 'aaa', 'road', 'shrine', 'stag', 'mara']);
    });

    it('keeps the marks of a placement together, and labels the first', () => {
      const s = layout(model, view());
      const first = s.prims.find((p) => p.entryId === 'stag');

      expect(first?.label).toBe('The Gilded Stag');
      expect(s.prims.filter((p) => p.label !== undefined)).toHaveLength(6);
      expect(s.prims.find((p) => p.entryId === 'river')?.label).toBe('The Rushwater, water');
      expect(s.prims.find((p) => p.entryId === 'town')?.label).toBe('Hollowmere, built-up area');
    });

    it('gives every primitive a distinct id', () => {
      const s = layout(model, view());

      expect(new Set(ids(s)).size).toBe(s.prims.length);
    });
  });

  describe('selection and hover', () => {
    it('only add a class: shapes, icons and numbers stay as they were', () => {
      const plain = layout(model, view());
      const marked = layout(model, view({ selection: 'stag', hover: 'town' }));
      const strip = (s: Scene) =>
        JSON.parse(JSON.stringify(s, (k, v) => (k === 'cls' ? undefined : v)));

      expect(strip(marked)).toEqual({ ...strip(plain), selection: 'stag' });
      expect(byId(marked, 'stag:0:pin').cls).toBe('m-pinbg m-on');
      expect(byId(marked, 'stag:0:icon').cls).toBe('m-ico m-on');
      expect(byId(marked, 'town:0:area').cls).toBe('m-region m-town m-hover');
      expect(byId(plain, 'stag:0:pin').cls).toBe('m-pinbg');
    });

    it('can be both on one mark', () => {
      const s = layout(model, view({ selection: 'stag', hover: 'stag' }));

      expect(byId(s, 'stag:0:pin').cls).toBe('m-pinbg m-on m-hover');
    });
  });

  describe("a placement's own style", () => {
    const parts = town.geometry.parts;
    const line = road.geometry.parts;
    const styled = (id: string, geometry: typeof parts, style: Style, role: string | null = null) =>
      place(id, id, [], geometry, { style, role });
    const draw = (p: ReturnType<typeof place>, v = view()) =>
      layout({ system, placements: [p] }, v);

    it('overrides the pattern: solid, dashed, dotted', () => {
      const solid = byId(
        draw(styled('s', line, { stroke: 'solid' }, 'route')),
        's:0:line',
      ) as PathPrim;
      const dashed = byId(
        draw(styled('d', line, { stroke: 'dashed' }, 'route')),
        'd:0:line',
      ) as PathPrim;
      const dotted = byId(draw(styled('t', parts, { stroke: 'dotted' })), 't:0:area') as PathPrim;

      expect(solid.dash).toBeUndefined();
      expect(dashed.dash).toBe('6 5');
      expect(dotted.dash).toBe('1 7');
      expect(dotted.cls).toContain('m-round');
    });

    it('overrides the weight in screen pixels', () => {
      const widths = (['hairline', 'thin', 'regular', 'thick', 'heavy'] as const).map(
        (weight) =>
          (byId(draw(styled('w', line, { weight }, 'route')), 'w:0:line') as PathPrim).strokeWidth,
      );

      expect(widths).toEqual([1, 1.5, 2, 3, 5]);
    });

    it('makes double two parallel strokes: an edge three times as wide and a gap over it', () => {
      const s = draw(styled('x', line, { stroke: 'double', weight: 'thin' }));

      expect(byId(s, 'x:0:line')).toMatchObject({ cls: 'm-line', strokeWidth: 4.5 });
      expect(byId(s, 'x:0:gap')).toMatchObject({ cls: 'm-gap', strokeWidth: 1.5 });

      const area = draw(styled('y', parts, { stroke: 'double' }));

      expect(ids(area).filter((id) => id.startsWith('y:'))).toEqual([
        'y:0:area',
        'y:0:edge',
        'y:0:gap',
      ]);
      expect(byId(area, 'y:0:area').cls).toContain('m-nostroke');
    });

    it('scales a river band by the weight', () => {
      const thick = draw(styled('r', river.geometry.parts, { weight: 'heavy' }, 'water'));

      expect((byId(thick, 'r:0:band') as PathPrim).strokeWidth).toBe(100);
    });

    it('makes none hit-only: no line of its own, a hairline outline while show places is on', () => {
      const withOutline = draw(styled('h', parts, { stroke: 'none' }, 'built-up'));
      const without = draw(
        styled('h', parts, { stroke: 'none' }, 'built-up'),
        view({ groups: { ...DEFAULT_GROUPS, showPlaces: false } }),
      );

      expect(ids(withOutline).filter((id) => id.startsWith('h:'))).toEqual([
        'h:0:hit',
        'h:0:outline',
      ]);
      expect(byId(withOutline, 'h:0:outline')).toMatchObject({ cls: 'm-outline', strokeWidth: 1 });
      expect(byId(withOutline, 'h:0:hit')).toMatchObject({ cls: 'm-hit', hit: { mode: 'area' } });
      expect(ids(without).filter((id) => id.startsWith('h:'))).toEqual(['h:0:hit']);
      expect(without.prims.find((p) => p.entryId === 'h')?.label).toBe('h, built-up area');
    });

    it('makes a hit-only line and a hit-only pin findable, too', () => {
      const l = draw(styled('l', line, { stroke: 'none' }, 'route'));
      const p = draw(styled('p', stag.geometry.parts, { stroke: 'none' }));

      expect(byId(l, 'l:0:hit').hit).toEqual({ mode: 'line', tol: 8 });
      expect(byId(p, 'p:0:hit')).toMatchObject({ kind: 'circle', r: 15, hit: { mode: 'area' } });
      expect(ids(p)).not.toContain('p:0:icon');
    });
  });

  it('names the initials of the first two words, upper-cased', () => {
    const s = layout(
      {
        system,
        placements: [
          place('a', 'ser tamsin the bold', [], [{ shape: 'point', at: [1, 1] }], {
            role: 'presence',
          }),
          place('b', 'Cher', [], [{ shape: 'point', at: [2, 2] }], { role: 'presence' }),
          place('c', 'Mill & Guild', [], [{ shape: 'point', at: [3, 3] }], { role: 'presence' }),
          place('d', '', [], [{ shape: 'point', at: [4, 4] }], { role: 'presence' }),
        ],
      },
      view(),
    );

    expect((byId(s, 'a:0:initials') as TextPrim).text).toBe('ST');
    expect((byId(s, 'b:0:initials') as TextPrim).text).toBe('C');
    expect((byId(s, 'c:0:initials') as TextPrim).text).toBe('MG');
    expect(ids(s)).not.toContain('d:0:initials');
  });

  it('puts a multi-part placement under one entry, with a mark per part', () => {
    const multi = place(
      'multi',
      'Multi',
      [],
      [
        { shape: 'circle', at: [100, 100], r: 30 },
        { shape: 'circle', at: [200, 100], r: 30 },
      ],
      { role: 'territory' },
    );
    const s = layout({ system, placements: [multi] }, view());

    expect(ids(s)).toEqual(['sheet', 'multi:0:area', 'multi:1:area']);
    expect(s.prims.filter((p) => p.label !== undefined)).toHaveLength(1);
  });
});
