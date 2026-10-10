// Which catalog titles a name probably means (ADR 0240): a score from 0 to 1 from the words the
// two share and the letters they share in threes, so "Torches" finds "Torch" and "healing
// potion" finds "Potion of Healing". Titles as typed; there is no translation here.

/** Lower case, no accents or punctuation, one space between words. */
export function normalize(text: string): string {
  return text
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim();
}

// A plural and its singular are one word.
const stem = (word: string) => (word.length > 3 ? word.replace(/(?:es|s)$/, '') : word);
const words = (text: string) => new Set(normalize(text).split(' ').filter(Boolean).map(stem));

function trigrams(text: string): Set<string> {
  const padded = `  ${normalize(text)} `;
  const grams = new Set<string>();

  for (let at = 0; at + 3 <= padded.length; at++) grams.add(padded.slice(at, at + 3));

  return grams;
}

function overlap(a: Set<string>, b: Set<string>): number {
  let shared = 0;

  for (const one of a) if (b.has(one)) shared++;

  return shared;
}

/** How alike two names are: 1 for the same name, 0 for nothing in common. */
export function score(name: string, title: string): number {
  const a = normalize(name);
  const b = normalize(title);

  if (!a || !b) return 0;
  if (a === b) return 1;

  const wordsA = words(name);
  const wordsB = words(title);
  const sharedWords = overlap(wordsA, wordsB);
  const jaccard = sharedWords / (wordsA.size + wordsB.size - sharedWords);
  const gramsA = trigrams(name);
  const gramsB = trigrams(title);
  const dice = (2 * overlap(gramsA, gramsB)) / (gramsA.size + gramsB.size);
  // One inside the other: "torch" in "torch, hooded", weighed by how much of it the other is.
  const inside =
    a.includes(b) || b.includes(a)
      ? 0.7 + 0.25 * (Math.min(a.length, b.length) / Math.max(a.length, b.length))
      : 0;

  return Math.max(inside, 0.6 * dice + 0.4 * jaccard);
}

/** The `count` best of `titles` for `name`, best first, leaving out those with little in common. */
export function suggest<T>(
  name: string,
  candidates: readonly T[],
  titleOf: (candidate: T) => string,
  count: number,
  least = 0.4,
): T[] {
  return candidates
    .map((candidate) => ({ candidate, points: score(name, titleOf(candidate)) }))
    .filter(({ points }) => points >= least)
    .sort((x, y) => y.points - x.points)
    .slice(0, count)
    .map(({ candidate }) => candidate);
}
