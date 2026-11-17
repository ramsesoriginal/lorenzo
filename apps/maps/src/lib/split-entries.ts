// Splitting a drawing into entries (ADR 0482): each part of a Location's drawing becomes a new
// Location, named from a base and numbered in drawing order, drawn with the part alone. Pure:
// what the page writes is worked out here and written by the editor.
import type { Geometry } from '@lorenzo/map-renderer';
import { LIMITS } from './validate';

/** The most parts one split takes: the writes of one batch (ADR 0351). */
export const MAX_SPLIT = LIMITS.batchOperations;

/** One new Location and the drawing it gets. */
export type SplitPiece = { name: string; geometry: Geometry };

/**
 * The pieces a drawing splits into, or why it cannot: it has one part, more parts than one batch
 * writes, or no name to number from.
 */
export function splitPieces(
  geometry: Geometry,
  base: string,
): { ok: true; pieces: SplitPiece[] } | { ok: false; why: string } {
  const name = base.trim();
  const count = geometry.parts.length;

  if (count < 2) return { ok: false, why: 'A drawing of one part is one entry already.' };

  if (count > MAX_SPLIT) {
    return {
      ok: false,
      why: `This drawing has ${count} parts, and one split makes at most ${MAX_SPLIT} entries. Remove some parts first.`,
    };
  }

  if (!name) return { ok: false, why: 'Give a name for the new places to be numbered from.' };

  return {
    ok: true,
    pieces: geometry.parts.map((part, index) => ({
      name: `${name} ${index + 1}`,
      geometry: { format: geometry.format, parts: [part] },
    })),
  };
}
