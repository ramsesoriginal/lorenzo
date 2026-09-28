// Giving a container with what's inside it, or only what's inside (ADR 0125):
// the question asked from a dry run's answer, and what's said once it's done.
// Pure, so the wording is tested without a page.
import type { ContentsResult } from './types';

function things(count: number): string {
  return `${count} ${count === 1 ? 'thing' : 'things'}`;
}

function givenCount(contents: readonly ContentsResult[]): number {
  return contents.filter((c) => c.status === 'ok').length;
}

/**
 * Whose the things that can't go stay: "1 thing inside stays Pia's." With
 * several owners: "3 things inside stay with their owners: 2 are Pia's, 1 is
 * Oskar's." Null when everything goes.
 */
export function keptNote(contents: readonly ContentsResult[]): string | null {
  const byOwner = new Map<string, number>();
  for (const content of contents) {
    if (content.status !== 'kept') continue;
    const owner = content.owner?.name ?? 'no one';
    byOwner.set(owner, (byOwner.get(owner) ?? 0) + 1);
  }
  const kept = [...byOwner.values()].reduce((sum, n) => sum + n, 0);
  if (kept === 0) return null;
  if (byOwner.size === 1) {
    const [owner] = byOwner.keys();
    return `${things(kept)} inside ${kept === 1 ? 'stays' : 'stay'} ${owner}'s.`;
  }
  const shares = [...byOwner].map(([owner, n]) => `${n} ${n === 1 ? 'is' : 'are'} ${owner}'s`);
  return `${things(kept)} inside stay with their owners: ${shares.join(', ')}.`;
}

function withKept(sentence: string, contents: readonly ContentsResult[]): string {
  const kept = keptNote(contents);
  return kept ? `${sentence} ${kept}` : sentence;
}

/**
 * Asked before giving a container with what's inside it, or null when there's
 * nothing inside to ask about (all of it is already the recipient's).
 */
export function withContentsQuestion(
  containerTitle: string,
  recipient: string,
  contents: readonly ContentsResult[],
): string | null {
  if (contents.length === 0) return null;
  const given = givenCount(contents);
  const sentence =
    given > 0
      ? `Give the ${containerTitle} and ${things(given)} inside it to ${recipient}?`
      : `Give the ${containerTitle} to ${recipient}? Nothing inside it can go along.`;
  return withKept(sentence, contents);
}

/** Said once a container went, with what could go along. */
export function withContentsDone(recipient: string, contents: readonly ContentsResult[]): string {
  const given = givenCount(contents);
  return withKept(
    given > 0 ? `Given to ${recipient}, with ${things(given)} inside.` : `Given to ${recipient}.`,
    contents,
  );
}

/**
 * Asked before giving only what's inside a container. Null when nothing inside
 * can be given; `nothingToGive` says why.
 */
export function contentsQuestion(
  containerTitle: string,
  recipient: string,
  contents: readonly ContentsResult[],
): string | null {
  const given = givenCount(contents);
  if (given === 0) return null;
  return withKept(`Give ${things(given)} inside the ${containerTitle} to ${recipient}?`, contents);
}

export function nothingToGive(
  containerTitle: string,
  recipient: string,
  contents: readonly ContentsResult[],
): string {
  if (contents.length === 0) {
    return `There's nothing inside the ${containerTitle} to give to ${recipient}.`;
  }
  return withKept(`Nothing inside the ${containerTitle} can be given.`, contents);
}

/** Said once what's inside went. */
export function contentsDone(
  containerTitle: string,
  recipient: string,
  contents: readonly ContentsResult[],
): string {
  return withKept(
    `Gave ${things(givenCount(contents))} inside the ${containerTitle} to ${recipient}.`,
    contents,
  );
}
