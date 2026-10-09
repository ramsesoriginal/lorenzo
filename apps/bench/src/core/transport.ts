// What the command layer needs from a server, as a small interface. The real one is built on the
// typed client (lib/transport.ts); the sample one keeps everything in memory (core/sample.ts).

export interface EntrySummary {
  id: string;
  name: string;
  kinds: string[];
}

/** An item as the server last said it was. `etag` is what `If-Match` wants on a write. */
export interface ItemState {
  id: string;
  name: string;
  parentIds: string[];
  etag: string | null;
}

export interface Transport {
  listEntries(): Promise<EntrySummary[]>;
  getItem(id: string): Promise<ItemState>;
  /** Writes, and answers with the item as it is after (a fresh `etag` included). */
  setName(id: string, name: string, etag: string | null): Promise<ItemState>;
  setParents(id: string, parentIds: string[], etag: string | null): Promise<ItemState>;
}

/** There is no connection: the command stays waiting and is tried again. */
export class OfflineError extends Error {
  constructor(message = 'No connection.') {
    super(message);
    this.name = 'OfflineError';
  }
}

/** The server said no. `precondition` is a stale `If-Match`: the item changed since it was read. */
export class RefusedError extends Error {
  readonly precondition: boolean;
  constructor(message: string, precondition = false) {
    super(message);
    this.name = 'RefusedError';
    this.precondition = precondition;
  }
}
