// A height and its unit (ADR 0473): what the API takes of them (ADR 0337), and the pair last used
// on a Map, kept in this browser. Pure, but for the two functions that read and write the store.

/** A value is finite, at most this large and of at most six decimals (ADR 0337). */
export const MAX_VALUE = 1_000_000_000_000;
export const MAX_UNIT_LENGTH = 32;

/** A typed height as the number the API takes, or null: empty, not a number, or too large. */
export function heightOf(text: string): number | null {
  const typed = text.trim();

  if (!/^-?(?:\d+(?:\.\d*)?|\.\d+)$/.test(typed)) return null;

  const value = Math.round(Number(typed) * 1e6) / 1e6;

  return Number.isFinite(value) && Math.abs(value) <= MAX_VALUE ? value : null;
}

/**
 * A typed unit as the API keeps it, or null: trimmed and composed, 1 to 32 characters, and none
 * of them a control character.
 */
export function unitOf(text: string): string | null {
  const unit = text.normalize('NFC').trim();

  if (unit === '' || [...unit].length > MAX_UNIT_LENGTH) return null;

  return /\p{C}/u.test(unit) ? null : unit;
}

export type Height = { value: number; unit: string };

const KEY = (mapId: string) => `lorenzo:maps:height:${mapId}`;

/** The pair as it is kept, and read back: anything else that is found there is no pair. */
export function heightFromText(raw: string | null): Height | null {
  if (!raw) return null;

  try {
    const kept = JSON.parse(raw) as { value?: unknown; unit?: unknown };
    const value = typeof kept.value === 'number' ? heightOf(String(kept.value)) : null;
    const unit = typeof kept.unit === 'string' ? unitOf(kept.unit) : null;

    return value !== null && unit !== null ? { value, unit } : null;
  } catch {
    return null;
  }
}

/** The height and unit last drawn on this Map in this browser, to be offered again. */
export function rememberedHeight(mapId: string): Height | null {
  try {
    return heightFromText(globalThis.localStorage?.getItem(KEY(mapId)) ?? null);
  } catch {
    return null;
  }
}

export function rememberHeight(mapId: string, height: Height): void {
  try {
    globalThis.localStorage?.setItem(KEY(mapId), JSON.stringify(height));
  } catch {
    // A browser that keeps nothing offers nothing the next time.
  }
}
