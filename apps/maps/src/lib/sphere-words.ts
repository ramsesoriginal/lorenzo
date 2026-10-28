// A sphere Map in words and in turns (ADR 0359): where a position is, which way a globe faces, and
// the projection a reader chose for themselves. Pure, so the page and the tests share it.
import type { Point, Projection, ProjectionKind } from '@lorenzo/map-renderer';

export const PROJECTION_WORDS: [ProjectionKind, string][] = [
  ['equirectangular', 'Flat'],
  ['mercator', 'Mercator'],
  ['orthographic', 'A globe'],
];

/** How far one press of a Turn button moves a globe, in degrees. */
export const TURN_STEP = 15;

export type Turn = 'west' | 'east' | 'north' | 'south';

const tenth = (n: number): number => Math.round(n * 10) / 10;

/** A position as people say it: `40.1° N, 12.5° E`, one decimal, hemispheres by letter. */
export function positionWords(point: Point): string {
  const lat = tenth(point[1]);
  const lon = tenth(point[0]);

  return `${Math.abs(lat).toFixed(1)}° ${lat < 0 ? 'S' : 'N'}, ${Math.abs(lon).toFixed(1)}° ${lon < 0 ? 'W' : 'E'}`;
}

function wrap(lon: number): number {
  const wrapped = ((((lon + 180) % 360) + 360) % 360) - 180;

  return wrapped === -180 && lon > 0 ? 180 : wrapped;
}

/** The centre of a globe after a turn: longitude wraps round, latitude stops at the poles. */
export function turned(centre: readonly [number, number], turn: Turn): [number, number] {
  const [lon, lat] = centre;

  switch (turn) {
    case 'west':
      return [wrap(lon - TURN_STEP), lat];
    case 'east':
      return [wrap(lon + TURN_STEP), lat];
    case 'north':
      return [lon, Math.min(90, lat + TURN_STEP)];
    default:
      return [lon, Math.max(-90, lat - TURN_STEP)];
  }
}

/** The projection a Map is saved with, as the renderer reads it. */
export function projectionFrom(view: unknown): Projection | undefined {
  const stored = (view as { projection?: Projection } | null | undefined)?.projection;

  return stored && typeof stored.kind === 'string' ? stored : undefined;
}

const KEY = (mapId: string) => `lorenzo:maps:projection:${mapId}`;

/** The projection this reader chose for one Map, or none. Kept in this browser only. */
export function readProjectionChoice(mapId: string): Projection | undefined {
  try {
    const stored = JSON.parse(localStorage.getItem(KEY(mapId)) ?? 'null') as Projection | null;

    return stored && PROJECTION_WORDS.some(([kind]) => kind === stored.kind) ? stored : undefined;
  } catch {
    return undefined;
  }
}

export function writeProjectionChoice(mapId: string, projection: Projection | undefined): void {
  try {
    if (projection) localStorage.setItem(KEY(mapId), JSON.stringify(projection));
    else localStorage.removeItem(KEY(mapId));
  } catch {
    // The choice is only remembered when the browser lets it be.
  }
}
