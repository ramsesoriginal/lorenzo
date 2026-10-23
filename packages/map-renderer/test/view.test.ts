import { describe, expect, it } from 'vitest';
import {
  centreOn,
  clampCentre,
  clampZoom,
  fitView,
  layout,
  MAX_ZOOM,
  MIN_ZOOM,
  PAN_STEP,
  panBy,
  placementCentre,
  sameView,
  screenToDrawing,
  ZOOM_STEP,
  zoomBy,
  zoomLabel,
  zoomTo,
} from '../src';
import { model, place, system, town, view } from './fixtures';

const vp = { width: 1000, height: 640 };
const whole = fitView(system);

describe('the view reducers', () => {
  it('clamps the zoom to 0.25 to 16, and a bad number to 1', () => {
    expect(clampZoom(100)).toBe(MAX_ZOOM);
    expect(clampZoom(0.01)).toBe(MIN_ZOOM);
    expect(clampZoom(Number.NaN)).toBe(1);
    expect(MIN_ZOOM).toBe(0.25);
    expect(MAX_ZOOM).toBe(16);
  });

  it('fits the whole map: zoom 1 at the centre of the sheet', () => {
    expect(whole).toEqual({ zoom: 1, centre: [500, 320] });
    expect(fitView({ ...system, extent: [-100, -50, 300, 150] })).toEqual({
      zoom: 1,
      centre: [100, 50],
    });
  });

  it('zooms about the centre, clamped', () => {
    expect(zoomTo(system, vp, whole, 3)).toEqual({ zoom: 3, centre: [500, 320] });
    expect(zoomBy(system, vp, whole, ZOOM_STEP).zoom).toBe(1.25);
    expect(zoomBy(system, vp, whole, 1000).zoom).toBe(MAX_ZOOM);
    expect(zoomBy(system, vp, whole, 0.0001).zoom).toBe(MIN_ZOOM);
    expect(zoomBy(system, vp, { zoom: MAX_ZOOM, centre: [1, 2] }, 2)).toEqual({
      zoom: MAX_ZOOM,
      centre: [1, 2],
    });
  });

  it('zooms toward an anchor: the drawing point under it stays under it', () => {
    const anchor: [number, number] = [800, 100];
    const before = screenToDrawing(system, vp, whole, anchor);
    const next = zoomTo(system, vp, whole, 4, anchor);
    const after = screenToDrawing(system, vp, next, anchor);

    expect(next.zoom).toBe(4);
    expect(after[0]).toBeCloseTo(before[0], 9);
    expect(after[1]).toBeCloseTo(before[1], 9);
  });

  it('pans by a drag: the drawing follows the pointer, so the centre moves the other way', () => {
    // At zoom 2 a screen pixel is half a drawing unit.
    const next = panBy(system, vp, { zoom: 2, centre: [500, 320] }, 100, -40);

    expect(next).toEqual({ zoom: 2, centre: [450, 340] });
  });

  it('pans by the arrow-key step in screen pixels', () => {
    expect(panBy(system, vp, whole, -PAN_STEP, 0).centre).toEqual([500 + PAN_STEP, 320]);
  });

  it('keeps the centre within the sheet and half a sheet around it', () => {
    expect(clampCentre(system, [10000, -10000])).toEqual([1500, -320]);
    expect(panBy(system, vp, whole, -1e6, 1e6).centre).toEqual([1500, -320]);
    expect(clampCentre(system, [10, 10])).toEqual([10, 10]);
  });

  it('centres on a point at the same zoom, unclamped', () => {
    expect(centreOn({ zoom: 3, centre: [1, 1] }, [9000, 9000])).toEqual({
      zoom: 3,
      centre: [9000, 9000],
    });
  });

  it('centres on a placement: the middle of its bounding box', () => {
    expect(placementCentre(town)).toEqual([500, 350]);
    expect(placementCentre(place('c', 'C', [], [{ shape: 'circle', at: [10, 20], r: 5 }]))).toEqual(
      [10, 20],
    );
    expect(placementCentre(place('e', 'E', [], []))).toBeNull();

    const next = centreOn({ zoom: 2, centre: [0, 0] }, placementCentre(town) ?? [0, 0]);
    const scene = layout(model, view({ zoom: next.zoom, centre: next.centre }));

    // The placement's centre lands in the middle of the viewport.
    expect(screenToDrawing(system, vp, next, [500, 320])).toEqual([500, 350]);
    expect(scene.width).toBe(1000);
  });

  it('maps a screen point to a drawing point and back through layout', () => {
    const state = { zoom: 2.5, centre: [412, 222] as [number, number] };
    const [x, y] = screenToDrawing(system, vp, state, [123, 456]);
    const scene = layout(
      { system, placements: [place('p', 'P', [], [{ shape: 'point', at: [x, y] }])] },
      view({ zoom: state.zoom, centre: state.centre }),
    );

    expect(scene.prims.find((p) => p.id === 'p:0:pin')).toMatchObject({ cx: 123, cy: 456 });
  });

  it('knows when nothing changed, and says the zoom as a percentage', () => {
    expect(sameView(whole, { zoom: 1, centre: [500, 320] })).toBe(true);
    expect(sameView(whole, { zoom: 2, centre: [500, 320] })).toBe(false);
    expect(zoomLabel(1.69)).toBe('169%');
    expect(zoomLabel(0.25)).toBe('25%');
  });
});
