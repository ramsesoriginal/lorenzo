// Undo across paragraphs (ADR 0511): one history of whole-text snapshots, so undo does not stop
// at the edge of the paragraph that happened to be open.

export class History {
  private past: string[] = [];
  private future: string[] = [];

  constructor(private readonly limit = 200) {}

  /** Remember `value`, the text before a change. A change clears what could be redone. */
  push(value: string): void {
    if (this.past[this.past.length - 1] === value) return;
    this.past.push(value);
    if (this.past.length > this.limit) this.past.shift();
    this.future = [];
  }

  /** The text before the last change, given the text now; null if there is none. */
  undo(current: string): string | null {
    const previous = this.past.pop();
    if (previous === undefined) return null;
    this.future.push(current);
    return previous;
  }

  redo(current: string): string | null {
    const next = this.future.pop();
    if (next === undefined) return null;
    this.past.push(current);
    return next;
  }

  get canUndo() {
    return this.past.length > 0;
  }

  get canRedo() {
    return this.future.length > 0;
  }
}
