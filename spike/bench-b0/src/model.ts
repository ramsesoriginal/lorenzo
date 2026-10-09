// The local view: the mirror with every pending command applied in order (RFC 0039 §2).
import { type Signal, signal } from "./signal";
import type { Store } from "./store";
import {
  type Command,
  type Entry,
  type Field,
  type RowView,
  STAT_KEYS,
} from "./types";

const same = (a: RowView, b: RowView) => JSON.stringify(a) === JSON.stringify(b);

export class Model {
  mirror = new Map<string, Entry>();
  commands: Command[] = [];
  rows = new Map<string, Signal<RowView>>();
  order: string[] = [];
  online = signal(true);
  channel = new BroadcastChannel("bench-b0");
  private writes: Promise<unknown> = Promise.resolve();
  /** How many row recomputations the last change caused (the spike's isolation measure). */
  recomputed = 0;
  readonly tab = crypto.randomUUID();
  /** Command ids with a write still queued: memory is newer than the store for these. */
  private dirty = new Map<string, number>();

  constructor(readonly store: Store) {}

  async load() {
    const entries = await this.store.mirrorAll();
    this.mirror = new Map(entries.map((e) => [e.id, e]));
    this.commands = (await this.store.outboxAll()).sort((a, b) => a.seq! - b.seq!);
    this.order = [...new Set([...entries.map((e) => e.id), ...this.commands.filter((c) => c.type === "entry.create").map((c) => c.entryId)])];
    for (const id of this.order) this.rows.set(id, signal(this.project(id), same));
  }

  /** Serialises IndexedDB writes; the UI never waits on them. */
  persist<T>(fn: () => Promise<T>): Promise<T> {
    const p = this.writes.then(fn);
    this.writes = p.catch(() => undefined);
    return p;
  }
  flush() {
    return this.writes;
  }

  project(id: string): RowView {
    const base = this.mirror.get(id);
    const mine = this.commands.filter((c) => c.entryId === id);
    let name = base?.name ?? "";
    const stats = { ...(base?.stats ?? { a: null, b: null, c: null }) };
    for (const c of mine) {
      if (c.type === "entry.create" && c.create) {
        name = c.create.name;
        Object.assign(stats, c.create.stats);
      } else if (c.field === "name") name = String(c.value ?? "");
      else if (c.field) stats[c.field as (typeof STAT_KEYS)[number]] = c.value as number | null;
    }
    const conflictCmd = mine.find((c) => c.state === "conflict");
    const attention = mine.some((c) => c.state === "attention");
    const state: RowView["state"] = conflictCmd
      ? "conflict"
      : attention
        ? "attention"
        : mine.length === 0
          ? "synced"
          : this.online.peek()
            ? "waiting"
            : "saved-on-device";
    return {
      id,
      name,
      stats,
      pending: mine.length,
      state,
      conflict: conflictCmd
        ? { cmdId: conflictCmd.id, field: conflictCmd.field!, base: conflictCmd.base, mine: conflictCmd.value, theirs: conflictCmd.theirs }
        : null,
    };
  }

  /** Recompute only the named rows; a row whose view did not change does not notify. */
  refresh(ids: Iterable<string>) {
    for (const id of ids) {
      this.recomputed++;
      const next = this.project(id);
      const s = this.rows.get(id);
      if (s) s.set(next);
      else {
        this.rows.set(id, signal(next, same));
        this.order.push(id);
      }
    }
  }
  refreshAll() {
    this.refresh(this.rows.keys());
  }

  announce() {
    this.channel.postMessage("changed");
  }

  // ---- user actions: each one is a command (no code path writes directly) -----------------

  edit(entryId: string, field: Field, raw: string) {
    const value: string | number | null = field === "name" ? raw : raw.trim() === "" ? null : Number(raw);
    if (typeof value === "number" && Number.isNaN(value)) return;
    const view = this.project(entryId);
    const before = field === "name" ? view.name : view.stats[field];
    if (before === value) return;
    // Coalesce: a still-waiting command on the same field keeps its original base.
    const open = this.commands.find((c) => c.entryId === entryId && c.field === field && c.state === "waiting" && c.tab === this.tab);
    let cmd: Command;
    if (open) {
      cmd = { ...open, value };
      this.commands[this.commands.indexOf(open)] = cmd;
    } else {
      const created = this.commands.find((c) => c.entryId === entryId && c.type === "entry.create" && c.state === "waiting");
      // base: the value the user saw (the mirror's); for an entry made offline there is none
      const mirrorEntry = this.mirror.get(entryId);
      const base = mirrorEntry ? (field === "name" ? mirrorEntry.name : mirrorEntry.stats[field]) : created ? before : null;
      cmd = { v: 1, type: "entry.set-field", id: crypto.randomUUID(), tab: this.tab, entryId, field, base, value, state: "waiting" };
      this.commands.push(cmd);
    }
    this.refresh([entryId]);
    this.writeCommand(cmd.id);
  }

  create(name: string): string {
    const entryId = crypto.randomUUID(); // client-made id (RFC 0039 W2)
    const cmd: Command = {
      v: 1, type: "entry.create", id: crypto.randomUUID(), tab: this.tab, entryId, base: null, value: null,
      create: { name, stats: { a: null, b: null, c: null } }, state: "waiting",
    };
    this.commands.push(cmd);
    this.order.unshift(entryId);
    this.refresh([entryId]);
    this.writeCommand(cmd.id);
    return entryId;
  }

  /** Writes the command as it is when its turn comes (the queue is serial, so a coalesced edit reuses the key). */
  writeCommand(id: string) {
    this.dirty.set(id, (this.dirty.get(id) ?? 0) + 1);
    return this.persist(async () => {
      try {
        const cur = this.commands.find((c) => c.id === id);
        if (!cur) return;
        const stored = await this.store.putCommand(cur);
        const i = this.commands.findIndex((c) => c.id === id);
        if (i >= 0) this.commands[i] = { ...this.commands[i], seq: stored.seq };
        this.announce();
      } finally {
        const n = (this.dirty.get(id) ?? 1) - 1;
        if (n <= 0) this.dirty.delete(id);
        else this.dirty.set(id, n);
      }
    });
  }

  /** A second tab changed the store: re-read it, update only rows whose view changed. */
  async reloadFromStore() {
    const [entries, stored] = await Promise.all([this.store.mirrorAll(), this.store.outboxAll()]);
    const touched = new Set<string>();
    for (const e of entries) {
      const old = this.mirror.get(e.id);
      if (!old || old.version !== e.version) touched.add(e.id);
      this.mirror.set(e.id, e);
    }
    // Merge, never replace: what this tab has not finished writing is newer than the store's copy
    // (a keystroke typed a moment ago must survive another tab's change).
    const mem = new Map(this.commands.map((c) => [c.id, c]));
    const next: Command[] = stored.map((c) => (this.dirty.has(c.id) && mem.has(c.id) ? { ...mem.get(c.id)!, seq: c.seq } : c));
    const seen = new Set(next.map((c) => c.id));
    const unwritten = this.commands.filter((c) => !seen.has(c.id) && this.dirty.has(c.id));
    const merged = [...next, ...unwritten].sort((a, b) => (a.seq ?? Infinity) - (b.seq ?? Infinity));
    for (const c of [...this.commands, ...merged]) touched.add(c.entryId);
    this.commands = merged;
    this.refresh(touched);
  }
}
