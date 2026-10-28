/**
 * A seeded source of numbers, so that what looks random (the arcs of a hill) is a function of an
 * entry's id and never stored. No `Math.random`, no clock.
 */

/** FNV-1a over the UTF-16 code units of `text`: a 32-bit hash. */
export function hashString(text: string): number {
  let h = 0x811c9dc5;

  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }

  return h >>> 0;
}

/** mulberry32: a small generator returning numbers in [0, 1). */
export function seeded(seed: string): () => number {
  let a = hashString(seed) || 0x9e3779b9;

  return () => {
    a = (a + 0x6d2b79f5) | 0;

    let t = Math.imul(a ^ (a >>> 15), 1 | a);

    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;

    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
