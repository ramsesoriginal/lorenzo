/** One sentence for a relationship, in words: who it ties, and which way (ADR 0408). */
export function relationshipSentence(row: {
  name: string;
  one_way: boolean;
  end_a: { name: string };
  end_b: { name: string };
}): string {
  const ties = row.one_way
    ? `From ${row.end_a.name} to ${row.end_b.name}`
    : `Between ${row.end_a.name} and ${row.end_b.name}, both ways`;
  return `${row.name}: ${ties}.`;
}
