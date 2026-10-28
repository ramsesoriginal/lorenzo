import { describe, expect, it } from 'vitest';
import {
  type BBox,
  DEFAULT_GROUPS,
  hitTest,
  type ImagePrim,
  isDataImage,
  type Layer,
  layerMatrix,
  layout,
  type MapModel,
  type Point,
  paintSvg,
  sceneToSvg,
  type View,
} from '../src';
import { fakeSvg } from './fakeDom';
import { place, system } from './fixtures';

const PNG = 'data:image/png;base64,AAAA';
const EXTENT: BBox = [0, 0, 1000, 640];

function layer(over: Partial<Layer> = {}): Layer {
  return { id: 'sea', href: PNG, size: [2000, 1000], ...over };
}

function apply(m: readonly number[], x: number, y: number): Point {
  return [
    (m[0] as number) * x + (m[2] as number) * y + (m[4] as number),
    (m[1] as number) * x + (m[3] as number) * y + (m[5] as number),
  ];
}

function near(a: readonly number[], b: readonly number[], eps = 1e-6): void {
  a.forEach((v, i) => {
    expect(Math.abs(v - (b[i] as number))).toBeLessThan(eps);
  });
}

function viewOf(over: Partial<View> = {}): View {
  return {
    viewport: { width: 1000, height: 640 },
    zoom: 1,
    centre: [500, 320],
    groups: { ...DEFAULT_GROUPS },
    selection: null,
    ...over,
  };
}

describe('where a picture lies on the sheet', () => {
  it('fits whole and centred when there is no calibration', () => {
    // 2000 x 1000 into 1000 x 640: scale 0.5, 500 tall, so 70 spare above and below.
    const m = layerMatrix(EXTENT, layer()) as unknown as number[];

    near(m, [0.5, 0, 0, 0.5, 0, 70]);
    // A tall picture is centred sideways.
    near(
      layerMatrix(EXTENT, layer({ size: [320, 640] })) as unknown as number[],
      [1, 0, 0, 1, 340, 0],
    );
  });

  it('is a turn, one scale and a move from two anchors', () => {
    // Picture 100 x 100. Its (0,0) and (1,0) go to (10,10) and (10,210): scale 2, turned a quarter.
    const m = layerMatrix(
      EXTENT,
      layer({
        size: [100, 100],
        calibration: {
          anchors: [
            { image: [0, 0], at: [10, 10] },
            { image: [1, 0], at: [10, 210] },
          ],
        },
      }),
    ) as unknown as number[];

    near(apply(m, 0, 0), [10, 10]);
    near(apply(m, 100, 0), [10, 210]);
    near(apply(m, 0, 100), [-190, 10]);
    // Lengths scale by one number whatever the direction.
    expect(Math.hypot(m[0] as number, m[1] as number)).toBeCloseTo(2, 6);
    expect(Math.hypot(m[2] as number, m[3] as number)).toBeCloseTo(2, 6);
  });

  it('uses the picture’s real proportions for fractions', () => {
    const m = layerMatrix(
      EXTENT,
      layer({
        size: [200, 100],
        calibration: {
          anchors: [
            { image: [0, 0], at: [0, 0] },
            { image: [1, 1], at: [200, 100] },
          ],
        },
      }),
    ) as unknown as number[];

    // The diagonal of a 200 x 100 picture is 1:1 on this sheet.
    near(m, [1, 0, 0, 1, 0, 0]);
  });

  it('is an affine map from three anchors, shear included', () => {
    const m = layerMatrix(
      EXTENT,
      layer({
        size: [100, 100],
        calibration: {
          anchors: [
            { image: [0, 0], at: [0, 0] },
            { image: [1, 0], at: [100, 0] },
            { image: [0, 1], at: [50, 100] },
          ],
        },
      }),
    ) as unknown as number[];

    near(apply(m, 0, 0), [0, 0]);
    near(apply(m, 100, 0), [100, 0]);
    near(apply(m, 0, 100), [50, 100]);
    near(apply(m, 100, 100), [150, 100]);
  });

  it('cannot be solved from anchors on top of one another or on a line', () => {
    const same = {
      anchors: [
        { image: [0.2, 0.2] as Point, at: [1, 1] as Point },
        { image: [0.2, 0.2] as Point, at: [5, 5] as Point },
      ],
    };
    const line = {
      anchors: [
        { image: [0, 0] as Point, at: [0, 0] as Point },
        { image: [0.5, 0.5] as Point, at: [1, 1] as Point },
        { image: [1, 1] as Point, at: [2, 2] as Point },
      ],
    };

    expect(layerMatrix(EXTENT, layer({ calibration: same }))).toBeNull();
    expect(layerMatrix(EXTENT, layer({ calibration: line }))).toBeNull();
    expect(layerMatrix(EXTENT, layer({ calibration: { anchors: [] } }))).toBeNull();
  });
});

describe('a picture in a Scene', () => {
  const model = (layers: readonly Layer[]): MapModel => ({
    system,
    placements: [place('p', 'Pin', ['location'], [{ shape: 'point', at: [100, 100] }])],
    layers,
  });

  it('is drawn above the sheet and below everything else, and is no target', () => {
    const scene = layout(model([layer()]), viewOf());
    const ids = scene.prims.map((p) => p.id);

    expect(ids.slice(0, 2)).toEqual(['sheet', 'layer:sea']);
    expect(ids.indexOf('layer:sea')).toBe(1);
    const image = scene.prims[1];

    expect(image).toMatchObject({ kind: 'image', cls: 'm-layer', width: 2000, height: 1000 });
    // 0.5 of the sheet's pixel scale, moved down 70 units.
    expect([...(image as ImagePrim).matrix]).toEqual([0.5, 0, 0, 0.5, 0, 70]);
    expect(image?.entryId).toBeUndefined();
    expect(hitTest(scene, [500, 320])).toBeNull();
  });

  it('follows the zoom and the pan', () => {
    const scene = layout(model([layer()]), viewOf({ zoom: 2, centre: [250, 160] }));
    const matrix = [...(scene.prims.find((p) => p.kind === 'image') as ImagePrim).matrix];

    // Scale doubles; the sheet's (250, 160) is at the middle of the 1000 x 640 viewport.
    near(matrix, [1, 0, 0, 1, 500 - 250 * 2, 320 - 160 * 2 + 140]);
  });

  it('keeps small scale entries that two decimals could not', () => {
    const scene = layout(model([layer({ size: [20000, 10000] })]), viewOf());
    const matrix = [...(scene.prims.find((p) => p.kind === 'image') as ImagePrim).matrix];

    expect(matrix[0]).toBe(0.05);
    const tiny = layout(model([layer({ size: [900000, 10000] })]), viewOf());
    const m = [...(tiny.prims.find((p) => p.kind === 'image') as ImagePrim).matrix];

    expect(m[0]).toBeGreaterThan(0);
  });

  it('is in the order given, with opacity, and the switch hides it', () => {
    const two = [layer({ id: 'a', opacity: 0.4 }), layer({ id: 'b' })];
    const scene = layout(model(two), viewOf());
    const images = scene.prims.filter((p) => p.kind === 'image');

    expect(images.map((p) => p.id)).toEqual(['layer:a', 'layer:b']);
    expect(images[0]).toMatchObject({ opacity: 0.4 });
    expect(images[1]).not.toHaveProperty('opacity');
    expect(
      layout(model(two), viewOf({ groups: { ...DEFAULT_GROUPS, layers: false } })).prims.some(
        (p) => p.kind === 'image',
      ),
    ).toBe(false);
  });

  it('draws only a data image, of a size, that can be placed', () => {
    for (const bad of [
      layer({ href: 'https://example.com/a.png' }),
      layer({ href: 'blob:https://example.com/x' }),
      layer({ href: 'javascript:alert(1)' }),
      layer({ href: 'data:text/html;base64,AAAA' }),
      layer({ size: [0, 100] }),
      layer({ size: [Number.NaN, 100] }),
      layer({
        calibration: {
          anchors: [
            { image: [0, 0], at: [1, 1] },
            { image: [0, 0], at: [2, 2] },
          ],
        },
      }),
    ]) {
      expect(layout(model([bad]), viewOf()).prims.some((p) => p.kind === 'image')).toBe(false);
    }

    expect(isDataImage('data:image/svg+xml;base64,AAAA')).toBe(true);
    expect(isDataImage('DATA:IMAGE/PNG,xx')).toBe(true);
    expect(isDataImage('data:image/png')).toBe(false);
  });

  it('is not drawn on a sphere, and a Map with no layer has the Scene it had', () => {
    const sphere: MapModel = {
      system: { kind: 'sphere', extent: [-180, -90, 180, 90] },
      placements: [],
      layers: [layer()],
    };

    expect(layout(sphere, viewOf()).prims.some((p) => p.kind === 'image')).toBe(false);

    const without = JSON.stringify(layout({ system, placements: model([]).placements }, viewOf()));

    expect(JSON.stringify(layout(model([]), viewOf()))).toBe(without);
  });

  it('is painted with its address written once and not compared again', () => {
    const scene = layout(model([layer()]), viewOf());
    const svg = sceneToSvg(scene);

    expect(svg).toContain('<image class="m-layer" data-key="sea:');
    expect(svg).toContain(`href="${PNG}"`);
    expect(svg).toContain('preserveAspectRatio="none"');

    const { svg: target, el } = fakeSvg();

    paintSvg(scene, target);

    const image = el.kids.find((c) => c.tagName === 'image');

    expect(image?.getAttribute('href')).toBe(PNG);
    // A pan changes the matrix but not which picture it is: the address is left alone.
    let writes = 0;
    const set = image?.setAttribute.bind(image);

    if (image && set) {
      image.setAttribute = (name: string, value: string) => {
        if (name === 'href') writes += 1;

        set(name, value);
      };
    }

    paintSvg(layout(model([layer()]), viewOf({ centre: [400, 320] })), target);
    expect(writes).toBe(0);
    expect(image?.getAttribute('transform')).not.toBeNull();
    // Another picture under the same name is written.
    paintSvg(layout(model([layer({ href: 'data:image/png;base64,BBBBBBBB' })]), viewOf()), target);
    expect(writes).toBe(1);
  });
});
