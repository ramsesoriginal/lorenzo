// One IndexedDB database per user (RFC 0039 §3), through a thin wrapper, no dependency.
import type { Command, Entry } from "./types";

const req = <T>(r: IDBRequest<T>) =>
  new Promise<T>((res, rej) => {
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  });
const done = (t: IDBTransaction) =>
  new Promise<void>((res, rej) => {
    t.oncomplete = () => res();
    t.onerror = () => rej(t.error);
    t.onabort = () => rej(t.error);
  });

export class Store {
  private constructor(
    readonly db: IDBDatabase,
    readonly name: string,
  ) {}

  static async open(userId: string): Promise<Store> {
    const name = `bench-b0:${userId}`;
    const open = indexedDB.open(name, 1);
    open.onupgradeneeded = () => {
      const db = open.result;
      db.createObjectStore("mirror", { keyPath: "id" });
      db.createObjectStore("outbox", { keyPath: "seq", autoIncrement: true });
      db.createObjectStore("meta");
    };
    return new Store(await req(open), name);
  }

  async mirrorAll(): Promise<Entry[]> {
    return req(this.db.transaction("mirror").objectStore("mirror").getAll());
  }
  async replaceMirror(entries: Entry[]): Promise<void> {
    const t = this.db.transaction("mirror", "readwrite");
    const s = t.objectStore("mirror");
    s.clear();
    for (const e of entries) s.put(e);
    return done(t);
  }
  async putMirror(entries: Entry[]): Promise<void> {
    const t = this.db.transaction("mirror", "readwrite");
    for (const e of entries) t.objectStore("mirror").put(e);
    return done(t);
  }
  async outboxAll(): Promise<Command[]> {
    return req(this.db.transaction("outbox").objectStore("outbox").getAll());
  }
  /** Adds or replaces; returns the stored command (with its seq). */
  async putCommand(c: Command): Promise<Command> {
    const t = this.db.transaction("outbox", "readwrite");
    const key = await req(t.objectStore("outbox").put(c));
    await done(t);
    return { ...c, seq: key as number };
  }
  async deleteCommand(seq: number): Promise<void> {
    const t = this.db.transaction("outbox", "readwrite");
    t.objectStore("outbox").delete(seq);
    return done(t);
  }
  async getMeta<T>(k: string): Promise<T | undefined> {
    return req(this.db.transaction("meta").objectStore("meta").get(k));
  }
  async setMeta(k: string, v: unknown): Promise<void> {
    const t = this.db.transaction("meta", "readwrite");
    t.objectStore("meta").put(v, k);
    return done(t);
  }
  close() {
    this.db.close();
  }
}
