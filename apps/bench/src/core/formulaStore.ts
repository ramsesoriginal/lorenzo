// The formulas the entries hold, read as they are looked at (ADR 0253). A formula is held by an
// entry and worked out for it and for everything that inherits from it, so finding the one that
// applies to an entry walks up its parents, own first.

import type { Formula } from './formulas';
import type { HeldFormula, Transport } from './transport';

/** Where the formula that applies to a stat on an entry is held: on the entry, or above it. */
export function findFormula(
  held: (entryId: string) => HeldFormula[] | undefined,
  parentsOf: (entryId: string) => string[],
  entryId: string,
  statId: string,
): HeldFormula | null {
  const seen = new Set<string>();
  const walk = (id: string): HeldFormula | null => {
    if (seen.has(id)) return null;
    seen.add(id);
    const own = held(id)?.find((h) => h.statId === statId);
    if (own) return own;
    for (const p of parentsOf(id)) {
      const found = walk(p);
      if (found) return found;
    }
    return null;
  };
  return walk(entryId);
}

export class FormulaStore {
  private byEntry = new Map<string, HeldFormula[]>();
  private tried = new Set<string>();

  constructor(
    private readonly transport: Transport,
    private readonly changed: () => void,
  ) {}

  held(entryId: string): HeldFormula[] | undefined {
    return this.byEntry.get(entryId);
  }

  /** Reads the formulas of the entries (once each, unless `again`, whether they were read or not). */
  async load(ids: string[], again = false): Promise<void> {
    const wanted = ids.filter((id) => again || !this.tried.has(id));
    if (!wanted.length) return;
    for (const id of wanted) this.tried.add(id);
    await Promise.all(
      wanted.map(async (id) => {
        try {
          this.byEntry.set(id, await this.transport.listFormulas(id));
        } catch {
          // Not read (offline, or the entry is not on the server yet): not asked again until it is
          // asked to (a failed read must not redraw the screen into asking again).
        }
      }),
    );
    this.changed();
  }

  async save(
    entryId: string,
    statId: string,
    formula: Formula,
    version: string | null,
  ): Promise<void> {
    const saved = await this.transport.setFormula(entryId, statId, formula, version);
    const rest = (this.byEntry.get(entryId) ?? []).filter((h) => h.statId !== statId);
    this.byEntry.set(entryId, [...rest, saved]);
    this.changed();
  }

  async remove(entryId: string, statId: string, version: string): Promise<void> {
    await this.transport.clearFormula(entryId, statId, version);
    this.byEntry.set(
      entryId,
      (this.byEntry.get(entryId) ?? []).filter((h) => h.statId !== statId),
    );
    this.changed();
  }
}
