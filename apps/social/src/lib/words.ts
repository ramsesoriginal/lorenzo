// The words a page uses for a relationship (ADR 0408): hierarchy and direction are said in words,
// never left to an arrow or a colour. Pure, so the tests need no page.

export interface Ends {
  endA: string;
  endB: string;
  oneWay: boolean;
}

/** How a relationship goes, in a few words. */
export function directionWords({ endA, endB, oneWay }: Ends): string {
  return oneWay ? `From ${endA} to ${endB}` : `Between ${endA} and ${endB}, both ways`;
}

/** A sentence that says the relationship. When the library says how its types read (the verb from
 * the first end, and from the second), the sentence is "Mara is the parent of Wren"; without them
 * it names the type, and without a type it only says who is tied to whom. */
export function sentence(
  ends: Ends,
  type?: { name: string; readsAs?: string | null; readsAsBack?: string | null } | null,
): string {
  const { endA, endB, oneWay } = ends;
  if (type?.readsAs) {
    const back = type.readsAsBack ? `; ${endB} ${type.readsAsBack} ${endA}` : '';
    return `${endA} ${type.readsAs} ${endB}${oneWay ? '' : back}`;
  }
  if (type) {
    return oneWay ? `${endA} → ${endB}: ${type.name}` : `${endA} and ${endB}: ${type.name}`;
  }
  return oneWay ? `${endA} to ${endB}` : `${endA} and ${endB}`;
}

/** The name a new relationship gets when the person does not give one: `<A> - <type> - <B>`. */
export function defaultName(endA: string, endB: string, type?: string | null): string {
  return type ? `${endA} - ${type} - ${endB}` : `${endA} - ${endB}`;
}

/** Who may see it, for the neutral badge. */
export function audienceWords(isPublic: boolean | null | undefined): string {
  if (isPublic === null || isPublic === undefined) return '';
  return isPublic ? 'Everyone in the library' : 'Restricted';
}
