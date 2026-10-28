// What a connection says from one of its ends (ADR 0365): where it goes, in words. Pure, so the pages
// and the tests share it.
export type Way = 'both' | 'out' | 'in';

type End = { id: string; name: string; slug?: string | null; kinds: readonly string[] };
type Joined = { end_a: End; end_b: End; one_way: boolean };

/** *to X* for a way both ways, *one way to X* when it leaves here, *one way from X* when it arrives. */
export function wayWords(way: Way, other: string): string {
  if (way === 'out') return `one way to ${other}`;
  if (way === 'in') return `one way from ${other}`;
  return `to ${other}`;
}

/** A connection seen from the entry `here`, one of its ends: which way it goes and the far end. */
export function seenFrom(connection: Joined, here: string): { way: Way; other: End } {
  const fromA = connection.end_a.id === here;
  const other = fromA ? connection.end_b : connection.end_a;
  if (!connection.one_way) return { way: 'both', other };
  return { way: fromA ? 'out' : 'in', other };
}
