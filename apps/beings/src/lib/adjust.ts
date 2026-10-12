// Changing a number while playing (RFC 0043): take away, add or set an amount, or step by one, and
// take any change back. The floor is the value of the stat the definition names as its minimum
// (ADR 0279); with none, nothing stops a number going below zero.

export type Operation = 'sub' | 'add' | 'set' | 'step-down' | 'step-up';

/** The value after an operation, never below `floor` when there is one. */
export function nextValue(
  old: number,
  operation: Operation,
  amount: number,
  floor: number | null,
): number {
  const next = {
    sub: old - amount,
    add: old + amount,
    set: amount,
    'step-down': old - 1,
    'step-up': old + 1,
  }[operation];

  return floor === null ? next : Math.max(floor, next);
}

/** What someone typed as an amount: a number of zero or more, or null when it is not one. */
export function parseAmount(text: string): number | null {
  const typed = text.trim().replace(',', '.');

  if (!/^\d+(\.\d+)?$/.test(typed)) return null;

  return Number(typed);
}

/** A change that can be taken back: what to tell the person, and how to undo it. */
export type Change = { label: string; undo: () => Promise<void> };

/** The last changes of a session, newest last; the oldest is forgotten past the limit. */
export class UndoStack {
  private changes: Change[] = [];

  constructor(private readonly limit = 30) {}

  push(change: Change): void {
    this.changes.push(change);

    if (this.changes.length > this.limit) this.changes.shift();
  }

  pop(): Change | undefined {
    return this.changes.pop();
  }

  get size(): number {
    return this.changes.length;
  }
}
