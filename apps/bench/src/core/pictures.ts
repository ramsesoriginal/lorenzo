// An entry's main picture (ADR 0243): shown, set, replaced and taken away. Online only, and not a
// command: the file is not kept anywhere to send later, and taking a picture away cannot be undone
// (the bytes are gone), so none of the outbox's promises could be kept for it.

import { OfflineError, type Transport } from './transport';

/** What the API takes (the same list profile pictures use). */
export const PICTURE_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif'];

/** How long after a failed read the next may be tried. */
const RETRY_MS = 10_000;

export class Pictures {
  /** The URL of each entry's picture that has been read; `null` for an entry that has none. */
  private urls = new Map<string, string | null>();
  private reading = new Set<string>();
  /** Entries whose picture is being written. */
  private writing = new Set<string>();
  private problems = new Map<string, string>();
  /** When a read last failed: not asked again at once, or a screen drawn after each would loop. */
  private failedAt = new Map<string, number>();

  constructor(
    private readonly transport: Transport,
    /** Tells the screen. */
    private readonly changed: () => void,
    /** Tells whatever remembers the picture (the links in text) that it is out of date. */
    private readonly forget: (id: string) => void,
    private readonly now: () => number = Date.now,
  ) {}

  /** The picture's URL, `null` for none, `undefined` until it has been read. */
  get(id: string): string | null | undefined {
    return this.urls.get(id);
  }
  busy(id: string): boolean {
    return this.writing.has(id);
  }
  problem(id: string): string | null {
    return this.problems.get(id) ?? null;
  }

  /** Reads it, once; a failed read is tried again next time. */
  async load(id: string): Promise<void> {
    if (this.urls.has(id) || this.reading.has(id)) return;
    const failed = this.failedAt.get(id);
    if (failed !== undefined && this.now() - failed < RETRY_MS) return;
    this.reading.add(id);
    try {
      this.urls.set(id, await this.transport.pictureOf(id));
      this.failedAt.delete(id);
      this.reading.delete(id);
      this.changed();
    } catch {
      // left unread, and said nothing about: the screen is not drawn again for it
      this.failedAt.set(id, this.now());
      this.reading.delete(id);
    }
  }

  /**
   * Reads it without telling the screen, for a thumbnail drawn in a list that a redraw of the page
   * would take away. Answers with the URL, or `null` for none or for a failed read.
   */
  async quiet(id: string): Promise<string | null> {
    const known = this.urls.get(id);
    if (known !== undefined) return known;
    try {
      const url = await this.transport.pictureOf(id);
      this.urls.set(id, url);
      return url;
    } catch {
      return null;
    }
  }

  /** Gives the entry this file as its picture. Says why not, rather than sending what is refused. */
  async set(id: string, file: File): Promise<void> {
    if (!PICTURE_TYPES.includes(file.type)) {
      this.problems.set(id, 'Choose a PNG, JPEG, WebP or GIF picture.');
      this.changed();
      return;
    }
    await this.write(id, () => this.transport.setPicture(id, file));
  }

  async clear(id: string): Promise<void> {
    await this.write(id, () => this.transport.clearPicture(id));
  }

  private async write(id: string, send: () => Promise<void>): Promise<void> {
    this.writing.add(id);
    this.problems.delete(id);
    this.changed();
    try {
      await send();
      // What was read is out of date; read again.
      this.urls.delete(id);
      this.forget(id);
    } catch (e) {
      this.problems.set(
        id,
        e instanceof OfflineError
          ? 'Pictures need a connection.'
          : e instanceof Error
            ? e.message
            : 'Could not save the picture.',
      );
    }
    this.writing.delete(id);
    this.changed();
    await this.load(id);
  }
}
