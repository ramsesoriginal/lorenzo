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

/** The view hint that means "the one that belongs to whoever this text belongs to" (ADR 0240). */
const MY = 'my';

/** One text, shown: its HTML, the link names in it that nothing has, and the `my/` ones nothing is held under. */
export interface Rendered {
  html: string;
  missing: string[];
  notMine: string[];
}

type Ref = { hint: string; slug: string };

/** What `{weight}` shows for the stats of one entry, by the slug of each stat's name. */
export type StatTexts = ReadonlyMap<string, { name: string; text: string; own: boolean }>;

export class LinkResolver {
  /** The stats of an entry as text, for the `{weight}` in its texts; null while it is not read. */
  stats: (home: string) => StatTexts | null = () => null;

  private found = new Map<string, ResolvedEntry>();
  private missed = new Map<string, number>();
  /** Main pictures by entry id, as URLs; `null` for an entry that has none. Kept for the visit. */
  private pictures = new Map<string, string | null>();
  /** When a `my/` answer was got: it depends on who holds what, so it is believed only a while. */
  private foundAt = new Map<string, number>();

  constructor(
    private readonly transport: Transport,
    private readonly now: () => number = Date.now,
  ) {}

  /**
   * What a reference is remembered under: its slug, or for `my/` the slug together with the entry
   * the text belongs to, since the same `my/longsword` means a different sword in each.
   */
  private keyOf(ref: Ref, home: string): string {
    return ref.hint === MY ? `${home}\u0000${MY}/${ref.slug}` : ref.slug;
  }

  private known(key: string): boolean {
    const at = this.foundAt.get(key) ?? this.missed.get(key);
    if (this.found.has(key) && !this.foundAt.has(key)) return true;
    return at !== undefined && this.now() - at < MISS_MS;
  }

  /** Asks about the references not asked about lately. A failed ask is simply tried again next time. */
  async lookUp(refs: Iterable<Ref>, home: string): Promise<void> {
    const wanted = new Map<string, Ref>();
    for (const ref of refs) {
      const key = this.keyOf(ref, home);
      if (!wanted.has(key) && !this.known(key)) wanted.set(key, ref);
    }
    const plain = [...wanted].filter(([, r]) => r.hint !== MY);
    const mine = [...wanted].filter(([, r]) => r.hint === MY);
    for (let i = 0; i < plain.length; i += MAX_SLUGS) {
      const batch = plain.slice(i, i + MAX_SLUGS);
      const rows = await this.transport.resolveSlugs(batch.map(([, r]) => r.slug));
      for (const [key] of batch) this.missed.set(key, this.now());
      for (const row of rows) {
        this.found.set(row.slug, row);
        this.missed.delete(row.slug);
      }
    }
    for (let i = 0; i < mine.length; i += MAX_SLUGS) {
      const batch = mine.slice(i, i + MAX_SLUGS);
      const rows = await this.transport.resolveSlugs(
        batch.map(([, r]) => `${MY}/${r.slug}`),
        home,
      );
      const answered = new Map(rows.map((row) => [row.slug, row]));
      for (const [key, ref] of batch) {
        const row = answered.get(`${MY}/${ref.slug}`);
        if (row) {
          this.found.set(key, row);
          this.missed.delete(key);
        } else {
          this.found.delete(key);
          this.missed.set(key, this.now());
        }
        this.foundAt.set(key, this.now());
      }
    }
  }

  /** Fetches the main pictures of the entries the image links name. A failed fetch is tried again. */
  private async loadPictures(refs: Iterable<Ref>, home: string): Promise<void> {
    const ids = new Set<string>();
    for (const ref of refs) {
      const id = this.found.get(this.keyOf(ref, home))?.id;
      if (id && !this.pictures.has(id)) ids.add(id);
    }
    await Promise.all(
      [...ids].map(async (id) => {
        try {
          this.pictures.set(id, await this.transport.pictureOf(id));
        } catch {
          // left unknown: asked again the next time
        }
      }),
    );
  }

  /** A picture was set or taken away: what was fetched for it is out of date. */
  forgetPicture(entryId: string) {
    this.pictures.delete(entryId);
  }

  /**
   * The entries a text links to or shows a picture of, each once, in the order they are named. The
   * ones nothing is called are left out. `home` is the entry the text belongs to (what `my/` means).
   */
  async linkedFrom(text: string, home: string): Promise<ResolvedEntry[]> {
    const refs = references(parse(text)).filter(isEntityRef);
    await this.lookUp(refs, home).catch(() => {});
    const seen = new Set<string>();
    const out: ResolvedEntry[] = [];
    for (const ref of refs) {
      const entry = this.found.get(this.keyOf(ref, home));
      if (entry && !seen.has(entry.id)) {
        seen.add(entry.id);
        out.push(entry);
      }
    }
    return out;
  }

  /** What the slug is, once looked up. */
  get(slug: string): ResolvedEntry | undefined {
    return this.found.get(slug);
  }

  /** The text with the links already looked up resolved: at once, for a preview that follows typing. */
  renderNow(text: string, home: string): Rendered {
    const doc = parse(text);
    const refs = references(doc).filter(isEntityRef);
    const entryOf = (ref: Ref) => this.found.get(this.keyOf(ref, home));
    return {
      html: render(doc, {
        resolve: {
          image: (ref) => {
            const entry = entryOf(ref);
            const src = entry && this.pictures.get(entry.id);
            return src ? { src, title: entry.name } : null;
          },
          stat: (name) => {
            const s = this.stats(home)?.get(name.toLowerCase());
            return s ? { text: s.text, title: s.name, class: s.own ? '' : 'inherited' } : null;
          },
          entity: (ref) => {
            const entry = entryOf(ref);
            return entry ? { href: entryHref(entry.id), title: entry.name } : null;
          },
        },
      }),
      missing: unique(
        refs
          .filter((r) => r.hint !== MY && this.missed.has(r.slug) && !this.found.has(r.slug))
          .map((r) => r.slug),
      ),
      notMine: unique(
        refs
          .filter((r) => {
            const key = this.keyOf(r, home);
            return r.hint === MY && this.missed.has(key) && !this.found.has(key);
          })
          .map((r) => r.slug),
      ),
    };
  }

  /**
   * The text as the reader sees it, its entry links resolved. `home` is the entry the text belongs
   * to, which is what `my/` means. Without a connection, as plain text.
   */
  async render(text: string, home: string): Promise<Rendered> {
    const refs = references(parse(text)).filter(isEntityRef);
    await this.lookUp(refs, home).catch(() => {});
    await this.loadPictures(
      refs.filter((r) => r.kind === 'image'),
      home,
    );
    return this.renderNow(text, home);
  }
}

const unique = (xs: string[]): string[] => [...new Set(xs)];
