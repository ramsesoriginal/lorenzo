import { describe, expect, it } from 'vitest';
import { hitTest, layout } from '../src';
import { model, place, system, town, view } from './fixtures';

const scene = layout(model, view());

describe('hitTest', () => {
  it('finds a pin by its disc, exactly', () => {
    expect(hitTest(scene, [400, 300])).toBe('stag');
    expect(hitTest(scene, [414, 300])).toBe('stag');
    // Just past the 15 pixel radius: it falls through to what is under (the town).
    expect(hitTest(scene, [416, 300])).toBe('town');
  });

  it('finds a person by a 12 pixel disc, above a pin', () => {
    expect(hitTest(scene, [410, 330])).toBe('mara');
    expect(hitTest(scene, [410, 341])).toBe('mara');
    expect(hitTest(scene, [410, 343])).toBe('town');
  });

  it('finds an area exactly, and not through its hole', () => {
    expect(hitTest(scene, [320, 220])).toBe('town');
    expect(hitTest(scene, [699, 499])).toBe('town');
    expect(hitTest(scene, [701, 501])).toBeNull();
    // The hole of the polygon is not the town.
    expect(hitTest(scene, [520, 380])).toBeNull();
  });

  it('finds a line within 8 pixels, and not beyond', () => {
    // The road runs (100,100) to (400,300): a point 5 pixels off it, then 12.
    const near = hitTest(scene, [250 - 3, 200 + 4]);

    expect(near).toBe('road');
    expect(hitTest(scene, [250 + 12, 200 - 10])).toBeNull();
  });

  it('finds a river by its band, half the band wide', () => {
    expect(hitTest(scene, [730 + 19, 60])).toBe('river');
    expect(hitTest(scene, [730 + 40, 60])).toBeNull();
  });

  it('prefers the topmost: a pin over the area, the area it is drawn on over the sheet', () => {
    expect(hitTest(scene, [400, 300])).toBe('stag');
    expect(hitTest(scene, [350, 250])).toBe('town');
  });

  it('prefers a higher z among areas', () => {
    const under = place('under', 'Under', [], town.geometry.parts, { role: 'territory', z: 1 });
    const over = place('over', 'Over', [], town.geometry.parts, { role: 'territory', z: 2 });
    const s = layout({ system, placements: [over, under] }, view());

    expect(hitTest(s, [320, 220])).toBe('over');
  });

  it('finds nothing on the sheet, and ignores labels', () => {
    expect(hitTest(scene, [5, 5])).toBeNull();
    // The label of the stag lies right of its disc, over nothing the stag owns.
    expect(hitTest(scene, [440, 300])).toBe('town');
  });

  it('finds a hit-only placement without drawing it', () => {
    const hidden = place('h', 'H', [], town.geometry.parts, {
      role: 'built-up',
      style: { stroke: 'none' },
    });
    const s = layout(
      { system, placements: [hidden] },
      view({
        groups: {
          places: true,
          people: true,
          roads: true,
          names: true,
          showPlaces: false,
          grid: true,
        },
      }),
    );

    expect(hitTest(s, [320, 220])).toBe('h');
    expect(hitTest(s, [10, 10])).toBeNull();
  });

  it('follows the view: after a zoom the disc is where the zoom put it', () => {
    const zoomed = layout(model, view({ zoom: 2, centre: [300, 200] }));

    expect(hitTest(zoomed, [700, 520])).toBe('stag');
    expect(hitTest(zoomed, [400, 300])).not.toBe('stag');
  });

  it('finds a curve by its flattened path', () => {
    const curve = place(
      'curve',
      'Curve',
      [],
      [
        {
          shape: 'bezier',
          start: [0, 0],
          segs: [
            [
              [0, 100],
              [100, 100],
              [100, 0],
            ],
          ],
        },
      ],
      { role: 'boundary' },
    );
    const s = layout({ system, placements: [curve] }, view({ zoom: 1 }));

    // The curve's lowest point is at t = 0.5: (50, 75).
    expect(hitTest(s, [50, 75])).toBe('curve');
    expect(hitTest(s, [50, 20])).toBeNull();
  });
});
