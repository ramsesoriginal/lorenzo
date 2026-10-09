// The outbox runner: serial, in the order written, pausing an entry on conflict (RFC 0039 §2, §5).
// One runner per user at a time, chosen with the Web Locks API; other tabs follow the store.
import type { Model } from "./model";
import { signal } from "./signal";
import type { Command, Entry } from "./types";

export const LOCK = "bench-b0-runner";
const eq = (a: unknown, b: unknown) => (a ?? null) === (b ?? null);
const fieldOf = (e: Entry, f: string) => (f === "name" ? e.name : e.stats[f as "a" | "b" | "c"]);

class Offline extends Error {}

async function call(method: string, path: string, body?: unknown, headers: Record<string, string> = {}) {
  try {
    const r = await fetch(`/api${path}`, {
      method,
      headers: { ...(body ? { "content-type": "application/json" } : {}), ...headers },
      body: body ? JSON.stringify(body) : undefined,
    });
    const text = await r.text();
    return { status: r.status, json: text ? JSON.parse(text) : null };
  } catch {
    throw new Offline();
  }
}

export class Runner {
  active = signal(false);
  passes = 0;
  sent: string[] = []; // what this runner actually put on the wire, for the tests
  private running = false;
  private again = false;
  private release: (() => void) | null = null;

  constructor(readonly model: Model) {
    model.channel.onmessage = async () => {
      await model.reloadFromStore();
      if (this.active.peek() && this.autoSync) void this.pass();
    };
  }
  autoSync = false;

  /** Becomes the runner when the lock is free; the lock is held until stop() or the tab closes. */
  start() {
    void navigator.locks.request(LOCK, () => {
      this.active.set(true);
      return new Promise<void>((res) => {
        this.release = () => {
          this.active.set(false);
          res();
        };
      });
    });
  }
  stop() {
    this.release?.();
  }

  async pass() {
    if (!this.active.peek()) return;
    if (this.running) {
      this.again = true;
      return;
    }
    this.running = true;
    try {
      do {
        this.again = false;
        this.passes++;
        await this.once();
      } while (this.again);
    } finally {
      this.running = false;
    }
  }

  private async once() {
    const m = this.model;
    await m.flush();
    const blocked = new Set<string>();
    const cache = new Map<string, Entry>();
    const touched = new Set<string>();
    let online = true;
    try {
      for (const queued of [...m.commands]) {
        if (queued.state !== "waiting") {
          blocked.add(queued.entryId); // an entry paused on a conflict waits; others carry on
          continue;
        }
        if (blocked.has(queued.entryId)) continue;
        const cmd = m.commands.find((c) => c.id === queued.id);
        if (!cmd || cmd.state !== "waiting") continue;
        const ok = await this.send(cmd, cache, touched);
        if (!ok) blocked.add(cmd.entryId);
      }
    } catch (e) {
      if (!(e instanceof Offline)) throw e;
      online = false;
    }
    m.online.set(online);
    await m.flush();
    m.refreshAll();
    m.announce();
  }

  private async finish(cmd: Command, entry: Entry, sentValue: unknown, touched: Set<string>) {
    const m = this.model;
    m.mirror.set(entry.id, entry);
    touched.add(entry.id);
    const now = m.commands.find((c) => c.id === cmd.id);
    if (now && cmd.type === "entry.set-field" && !eq(now.value, sentValue)) {
      // edited while in flight: it stays queued, with what the server now has as its base
      now.base = sentValue as Command["base"];
      await m.persist(() => m.store.putMirror([entry]));
      await m.writeCommand(now.id);
      return;
    }
    m.commands = m.commands.filter((c) => c.id !== cmd.id);
    await m.persist(async () => {
      await m.store.putMirror([entry]);
      if (cmd.seq !== undefined) await m.store.deleteCommand(cmd.seq);
    });
  }

  private async send(cmd: Command, cache: Map<string, Entry>, touched: Set<string>): Promise<boolean> {
    const m = this.model;
    const attention = async (error: string) => {
      cmd.state = "attention";
      cmd.error = error;
      touched.add(cmd.entryId);
      await m.writeCommand(cmd.id);
      return false;
    };

    if (cmd.type === "entry.create") {
      this.sent.push(`POST ${cmd.entryId}`);
      const r = await call("POST", "/entries", { id: cmd.entryId, ...cmd.create });
      // 201 created, 200 the same id already there (a replay after a lost response): both are success
      if (r.status === 200 || r.status === 201) {
        await this.finish(cmd, r.json, null, touched);
        return true;
      }
      return attention(`create refused: ${r.status}`);
    }

    for (let attempt = 0; attempt < 2; attempt++) {
      let server = cache.get(cmd.entryId);
      if (!server) {
        const g = await call("GET", `/entries/${cmd.entryId}`);
        if (g.status === 404) return attention("entry no longer exists");
        server = g.json as Entry;
        cache.set(cmd.entryId, server);
      }
      const theirs = fieldOf(server, cmd.field!);
      if (eq(theirs, cmd.value)) {
        // already there: also how a replayed command resolves
        await this.finish(cmd, server, cmd.value, touched);
        return true;
      }
      if (!eq(theirs, cmd.base)) {
        cmd.state = "conflict";
        cmd.theirs = theirs;
        m.mirror.set(server.id, server); // the mirror is the last known server state; now we know it
        touched.add(cmd.entryId);
        await m.persist(() => m.store.putMirror([server!]));
        await m.writeCommand(cmd.id);
        return false;
      }
      this.sent.push(`PATCH ${cmd.entryId} ${cmd.field}`);
      const r = await call("PATCH", `/entries/${cmd.entryId}`, { field: cmd.field, value: cmd.value }, { "if-match": server.version });
      if (r.status === 200) {
        cache.set(cmd.entryId, r.json);
        await this.finish(cmd, r.json, cmd.value, touched);
        return true;
      }
      if (r.status === 412) {
        cache.delete(cmd.entryId); // changed between the read and the write: compare again
        continue;
      }
      return attention(`write refused: ${r.status}`);
    }
    return attention("kept changing under it");
  }

  // ---- the three-way choice ---------------------------------------------------------------

  async resolve(cmdId: string, choice: "mine" | "theirs") {
    const m = this.model;
    const cmd = m.commands.find((c) => c.id === cmdId);
    if (!cmd) return;
    if (choice === "mine") {
      cmd.base = cmd.theirs;
      cmd.theirs = undefined;
      cmd.state = "waiting";
      await m.writeCommand(cmd.id);
    } else {
      m.commands = m.commands.filter((c) => c.id !== cmdId);
      await m.persist(async () => {
        if (cmd.seq !== undefined) await m.store.deleteCommand(cmd.seq);
      });
    }
    m.refresh([cmd.entryId]);
    m.announce();
    if (choice === "mine") void this.pass();
  }
}
