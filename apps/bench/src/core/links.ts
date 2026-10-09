// What the entry links in LorenzoScript text lead to (ADR 0105): the slugs a text names are looked
// up on the server in batches and remembered, so a preview that follows the typing asks only about
// what it has not seen. Rendering is here too, since it is the lookup that makes it async.

import { type EntityRef, parse, type Reference, references, render } from '@lorenzo/lorenzoscript';
import type { ResolvedEntry, Transport } from './transport';

/** GET .../entities/resolve takes at most this many slugs (ADR 0107). */
const MAX_SLUGS = 100;
/** How long a slug that nothing holds is believed: an entry may be made, or named, any moment. */
const MISS_MS = 30_000;

/** Where a link to an entry leads inside Bench: a fragment the shell turns into opening it. */
export const entryHref = (id: string): string => `#entry-${id}`;
export const entryIdOfHref = (href: string | null): string | null =>
  href?.startsWith('#entry-') ? href.slice('#entry-'.length) : null;

const isEntityRef = (ref: Reference): ref is Reference & EntityRef =>
  ref.kind === 'entity' || ref.kind === 'image';

/** One text, shown: its HTML, and the link names in it that nothing has. */
export interface Rendered {
  html: string;
  missing: string[];
}

export class LinkResolver {
  private found = new Map<string, ResolvedEntry>();
  private missed = new Map<string, number>();

  constructor(
    private readonly transport: Transport,
    private readonly now: () => number = Date.now,
  ) {}

  private known(slug: string): boolean {
    if (this.found.has(slug)) return true;
    const at = this.missed.get(slug);
    return at !== undefined && this.now() - at < MISS_MS;
  }

  /** Asks about the slugs not asked about lately. A failed ask is simply tried again next time. */
  async lookUp(slugs: Iterable<string>): Promise<void> {
    const wanted = [...new Set(slugs)].filter((s) => !this.known(s));
    for (let i = 0; i < wanted.length; i += MAX_SLUGS) {
      const batch = wanted.slice(i, i + MAX_SLUGS);
      const rows = await this.transport.resolveSlugs(batch);
      for (const slug of batch) this.missed.set(slug, this.now());
      for (const row of rows) {
        this.found.set(row.slug, row);
        this.missed.delete(row.slug);
      }
    }
  }

  /** What the slug is, once looked up. */
  get(slug: string): ResolvedEntry | undefined {
    return this.found.get(slug);
  }

  /** The text with the links already looked up resolved: at once, for a preview that follows typing. */
  renderNow(text: string): Rendered {
    const doc = parse(text);
    const slugs = references(doc)
      .filter(isEntityRef)
      .map((r) => r.slug);
    return {
      html: render(doc, {
        resolve: {
          entity: ({ slug }) => {
            const entry = this.found.get(slug);
            return entry ? { href: entryHref(entry.id), title: entry.name } : null;
          },
        },
      }),
      missing: [...new Set(slugs)].filter((s) => this.missed.has(s) && !this.found.has(s)),
    };
  }

  /** The text as the reader sees it, its entry links resolved. Without a connection, as plain text. */
  async render(text: string): Promise<Rendered> {
    const slugs = references(parse(text))
      .filter(isEntityRef)
      .map((r) => r.slug);
    await this.lookUp(slugs).catch(() => {});
    return this.renderNow(text);
  }
}
