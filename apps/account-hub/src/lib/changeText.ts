// What a row of the change feed says (ADR 0099), as a sentence. Pure and dependency-free like
// format.ts. The actor is never named: the API gives one only for another player, and a GM's
// action must read as what happened, not who did it.
import type { EntityChange } from './types';

// `character` is whose it was, named by the page from what GET /me says.
export function describeChange(
  change: Pick<EntityChange, 'kind' | 'entity_name'>,
  character: string,
): string {
  const item = change.entity_name;
  const held = `${item}, held by ${character},`;

  switch (change.kind) {
    case 'received':
      return `${character} received ${item}.`;
    case 'given_away':
      return `${character} no longer has ${item}.`;
    case 'moved':
      return `${held} was moved.`;
    case 'split':
      return `${held} was split.`;
    case 'merged':
      return `${held} was merged with another stack.`;
    case 'renamed':
      return `${held} was renamed.`;
    case 'deleted':
      return `${held} was deleted.`;
    default:
      // A kind this page doesn't know yet still says which item and whose.
      return `Something changed about ${item}, held by ${character}.`;
  }
}
