import { describe, expect, it } from 'vitest';
import {
  DEFAULT_GROUPS,
  GLOBE_RADIUS,
  isVisible,
  layout,
  type MapModel,
  MERCATOR_LIMIT,
  type Point,
  type Projection,
  projectLonLat,
  type System,
  unprojectPoint,
  type View,
} from '../src';
import { extentOf, project, unproject } from '../src/project';
import { densify, projectedRuns } from '../src/sphere';
import { place } from './fixtures';

const flat: Projection = { kind: 'equirectangular' };
const mercator: Projection = { kind: 'mercator' };
const globe = (lon = 0, lat = 0): Projection => ({ kind: 'orthographic', centre: [lon, lat] });

function near(a: readonly number[], b: readonly number[], eps = 1e-6): void {
  expect(a.length).toBe(b.length);
  a.forEach((v, i) => {
    expect(Math.abs(v - (b[i] as number))).toBeLessThan(eps);
  });
}

function sphere(projection?: Projection): System {
  return {
    kind: 'sphere',
    extent: [-180, -90, 180, 90],
    ...(projection ? { projection } : {}),
  };
}

function viewOf(over: Partial<View> = {}): View {
  return {
    viewport: { width: 800, height: 600 },
    zoom: 1,
    centre: [0, 0],
    groups: { ...DEFAULT_GROUPS },
    selection: null,
    ...over,
  };
}

describe('the projections', () => {
  it('draw the origin at the origin and flip latitude', () => {
    near(projectLonLat(flat, 0, 0), [0, 0]);
    near(projectLonLat(flat, 12.5, 40), [12.5, -40]);
    near(projectLonLat(mercator, 0, 0), [0, 0]);
    near(projectLonLat(globe(), 0, 0), [0, 0]);
  });

  it('draw Mercator by the usual formula and hold it to its limit', () => {
    const [, y] = projectLonLat(mercator, 0, 45);

    expect(y).toBeCloseTo(-(Math.log(Math.tan(Math.PI / 4 + Math.PI / 8)) * 180) / Math.PI, 6);
    expect(projectLonLat(mercator, 0, MERCATOR_LIMIT)[1]).toBeCloseTo(-180, 4);
    expect(projectLonLat(mercator, 0, 90)[1]).toBeCloseTo(-180, 4);
    expect(projectLonLat(mercator, 0, -90)[1]).toBeCloseTo(180, 4);
  });

  it('draw the globe: east is right, north is up, and 90 degrees away is the limb', () => {
    near(projectLonLat(globe(), 90, 0), [GLOBE_RADIUS, 0]);
    near(projectLonLat(globe(), -90, 0), [-GLOBE_RADIUS, 0]);
    near(projectLonLat(globe(), 0, 90), [0, -GLOBE_RADIUS]);
    near(projectLonLat(globe(), 0, -90), [0, GLOBE_RADIUS]);
    // Turned to face 90 degrees east, longitude 90 is in the middle.
    near(projectLonLat(globe(90, 0), 90, 0), [0, 0]);
    // Seen from the north pole, the pole is in the middle and the equator is the limb.
    near(projectLonLat(globe(0, 90), 0, 90), [0, 0]);
    expect(Math.hypot(...(projectLonLat(globe(0, 90), 33, 0) as [number, number]))).toBeCloseTo(
      GLOBE_RADIUS,
      6,
    );
  });

  it('know what the globe shows and move what is behind it onto the limb', () => {
    expect(isVisible(globe(), 0, 0)).toBe(true);
    expect(isVisible(globe(), 89, 0)).toBe(true);
    expect(isVisible(globe(), 91, 0)).toBe(false);
    expect(isVisible(globe(), 180, 0)).toBe(false);
    expect(isVisible(flat, 180, 0)).toBe(true);

    for (const [lon, lat] of [
      [170, 10],
      [180, 0],
      [-150, -60],
    ] as Point[]) {
      expect(Math.hypot(...(projectLonLat(globe(), lon, lat) as [number, number]))).toBeCloseTo(
        GLOBE_RADIUS,
        6,
      );
    }
  });

  it('have the sheet they say', () => {
    expect(extentOf(sphere())).toEqual([-180, -90, 180, 90]);
    expect(extentOf(sphere(mercator))).toEqual([-180, -180, 180, 180]);
    expect(extentOf(sphere(globe()))).toEqual([-100, -100, 100, 100]);
    // A system that is not a sphere is untouched.
    expect(extentOf({ kind: 'plane', extent: [0, 0, 10, 6] })).toEqual([0, 0, 10, 6]);
    expect(project({ kind: 'plane', extent: [0, 0, 10, 6] }, [3, 4])).toEqual([3, 4]);
    expect(unproject({ kind: 'plane', extent: [0, 0, 10, 6] }, [3, 4])).toEqual([3, 4]);
  });

  it('are undone by their inverse over a lattice of positions', () => {
    const lattice: Point[] = [];

    for (let lon = -170; lon <= 170; lon += 20) {
      for (let lat = -80; lat <= 80; lat += 20) lattice.push([lon, lat]);
    }

    for (const projection of [flat, mercator, globe(), globe(40, -30), globe(-120, 60)]) {
      for (const [lon, lat] of lattice) {
        if (!isVisible(projection, lon, lat)) continue;

        const [x, y] = projectLonLat(projection, lon, lat);
        const back = unprojectPoint(projection, x, y);

        near(back, [lon, lat], 1e-4);
      }
    }
  });

  it('clamp a point off the sheet and move one off the globe onto its limb', () => {
    expect(unprojectPoint(flat, 500, -500)).toEqual([180, 90]);
    expect(unprojectPoint(mercator, -500, 500)[0]).toBe(-180);
    expect(Math.abs(unprojectPoint(mercator, 0, 500)[1])).toBeLessThanOrEqual(MERCATOR_LIMIT);

    const [lon, lat] = unprojectPoint(globe(), 500, 0);

    near([lon, lat], [90, 0], 1e-6);
    near(unprojectPoint(globe(20, 30), 0, 0), [20, 30]);
  });
});

describe('segments', () => {
  it('are straight in longitude and latitude, so a flat projection adds no samples', () => {
    const line: Point[] = [
      [0, 0],
      [100, 50],
    ];

    expect(densify(flat, line, false)).toEqual(line);
    expect(densify(mercator, line, false).length).toBeGreaterThan(40);
    near(densify(mercator, line, false)[1] as Point, [2, 1]);
  });

  it('are cut where they go behind the globe, ending on the limb', () => {
    const samples = densify(
      globe(),
      [
        [-60, 0],
        [120, 0],
      ],
      false,
    );
    const runs = projectedRuns(globe(), samples);

    expect(runs).toHaveLength(1);

    const run = runs[0] as Point[];
    const last = run[run.length - 1] as Point;

    expect(Math.hypot(last[0], last[1])).toBeCloseTo(GLOBE_RADIUS, 4);
    expect(run[0]?.[0]).toBeCloseTo(-GLOBE_RADIUS * Math.sin((60 * Math.PI) / 180), 4);
    // Wholly behind it, nothing is drawn.
    expect(
      projectedRuns(
        globe(),
        densify(
          globe(),
          [
            [120, 0],
            [170, 20],
          ],
          false,
        ),
      ),
    ).toEqual([]);
    // In and out and in again is two runs.
    const split = projectedRuns(
      globe(),
      densify(
        globe(),
        [
          [-40, 0],
          [140, 0],
          [140, 60],
          [30, 60],
        ],
        false,
      ),
    );

    expect(split.length).toBeGreaterThanOrEqual(2);
  });
});

describe('a sphere in a Scene', () => {
  const river = place(
    'river',
    'The Long River',
    ['location'],
    [
      {
        shape: 'polyline',
        pts: [
          [-20, -10],
          [30, 40],
        ],
      },
    ],
  );
  const town = place('town', 'Hollowmere', ['location'], [{ shape: 'point', at: [10, 20] }]);
  const behind = place('behind', 'Far Side', ['location'], [{ shape: 'point', at: [170, 0] }]);
  const region = place(
    'region',
    'The Marches',
    ['location'],
    [
      {
        shape: 'polygon',
        rings: [
          [
            [-30, -20],
            [30, -20],
            [30, 20],
            [-30, 20],
          ],
        ],
      },
    ],
    { role: 'territory' },
  );

  function modelOf(projection?: Projection, placements = [river, town, behind, region]): MapModel {
    return { system: sphere(projection), placements };
  }

  it('draws a flat sphere with the longitude as x and the latitude, flipped, as y', () => {
    const scene = layout(modelOf(), viewOf());
    const pin = scene.prims.find((p) => p.id.startsWith('town:'));

    expect(pin).toBeDefined();
    // 800 x 600 holds 360 x 180 at 2.2222 pixels a degree: the sheet is 800 x 400, centred.
    const pins = scene.prims.filter((p) => p.entryId === 'town' && p.kind === 'circle');

    const first = pins[0] as { cx: number; cy: number };

    expect(first.cx).toBeCloseTo(400 + 10 * (800 / 360), 1);
    expect(first.cy).toBeCloseTo(300 - 20 * (800 / 360), 1);
    expect(scene.prims.some((p) => p.id === 'limb')).toBe(false);
    expect(scene.prims.find((p) => p.id === 'grid')?.cls).toBe('m-grid');
  });

  it('is the same bytes for the same input and holds the Grid switch', () => {
    const a = JSON.stringify(layout(modelOf(mercator), viewOf()));

    expect(JSON.stringify(layout(modelOf(mercator), viewOf()))).toBe(a);
    expect(
      layout(modelOf(), viewOf({ groups: { ...DEFAULT_GROUPS, grid: false } })).prims.some(
        (p) => p.id === 'grid',
      ),
    ).toBe(false);
  });

  it('draws the globe with its limb, drops a pin behind it and keeps one in front', () => {
    const scene = layout(modelOf(globe()), viewOf());

    expect(scene.prims.find((p) => p.id === 'limb')).toMatchObject({
      kind: 'circle',
      cls: 'm-limb',
    });
    expect(scene.prims.some((p) => p.entryId === 'town')).toBe(true);
    expect(scene.prims.some((p) => p.entryId === 'behind')).toBe(false);
    // The area and the line are both drawn, inside the disc.
    for (const id of ['river', 'region']) {
      const mark = scene.prims.find((p) => p.entryId === id && p.kind === 'path');

      expect(mark).toBeDefined();
    }

    const limb = scene.prims.find((p) => p.id === 'limb') as { cx: number; cy: number; r: number };

    for (const p of scene.prims) {
      if (!p.entryId || p.kind !== 'path') continue;

      const [x0, y0, x1, y1] = p.bbox;

      for (const [x, y] of [
        [x0, y0],
        [x1, y1],
      ] as Point[]) {
        expect(Math.hypot(x - limb.cx, y - limb.cy)).toBeLessThanOrEqual(limb.r + 3);
      }
    }
  });

  it('turns the globe by its projection centre alone', () => {
    const faced = layout(modelOf(globe(170, 0)), viewOf());

    expect(faced.prims.some((p) => p.entryId === 'behind')).toBe(true);
    expect(faced.prims.some((p) => p.entryId === 'town')).toBe(false);
  });

  it('draws a curve and a circle as nothing, which a sphere does not hold', () => {
    const odd = place('odd', 'Odd', ['location'], [{ shape: 'circle', at: [0, 0], r: 5 }]);

    expect(layout(modelOf(undefined, [odd]), viewOf()).prims.some((p) => p.entryId === 'odd')).toBe(
      false,
    );
  });

  it('spaces its lines by the zoom and draws every line of a flat sphere as a straight one', () => {
    const wide = layout(modelOf(undefined, []), viewOf());
    const close = layout(modelOf(undefined, []), viewOf({ zoom: 8 }));
    const count = (d: string): number => (d.match(/M/g) ?? []).length;
    const dOf = (scene: ReturnType<typeof layout>): string =>
      (scene.prims.find((p) => p.id === 'grid') as { d: string }).d;

    expect(count(dOf(close))).toBeGreaterThan(count(dOf(wide)));
    expect(dOf(wide)).not.toContain(' C ');
  });

  it("keeps the globe's lines to the front", () => {
    const scene = layout(modelOf(globe(), []), viewOf());
    const d = (scene.prims.find((p) => p.id === 'grid') as { d: string }).d;

    expect(d.length).toBeGreaterThan(100);
    expect(scene.prims.map((p) => p.id).slice(0, 3)).toEqual(['sheet', 'limb', 'grid']);
  });
});
