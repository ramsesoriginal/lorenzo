// Descriptions as LorenzoScript (RFC 0027, ADR 0108): rendering them with
// this tenant's entities resolved, and what links to an entity. Writing
// them is information.ts's.
import {
  parse,
  type Reference,
  type Resolver,
  references,
  render,
  slugify,
  statNames,
} from '@lorenzo/lorenzoscript';
import { client, type components, fetchAllPages, MAX_PAGE_SIZE, unwrap } from './api';
import { loadAppLinks } from './appLinks';
import { type EntityReference, entityHref, linkNote, type ResolvedSlug } from './entityLinks';
import { viewerLocales } from './me';

type Entity = components['schemas']['EntityDetailOut'];
type Payload = Entity['information'][number]['payloads'][number];

/** One text's HTML, and what an author should know about links in it that won't work. */
export type Rendered = { html: string; notes: string[] };
/**
 * Renders texts; `homes` says which entity each text belongs to, which is what a `my/` link is
 * held by (ADR 0240). A text with none, a new one say, has no `my/` meaning.
 */
export type Renderer = (
  texts: string[],
  homes?: readonly (string | undefined)[],
) => Promise<Rendered[]>;

/** The renderer for texts that all belong to `home`. */
export const at =
  (renderer: Renderer, home: string | undefined): Renderer =>
  (texts) =>
    renderer(
      texts,
      texts.map(() => home),
    );

/** The view hint that means "held by whoever the text belongs to" (ADR 0240). */
const MY = 'my';
/** How long a `my/` answer is believed: who holds what changes while a page is open. */
const MY_MS = 30_000;
/** How long the stats of an entry are believed, for the `{weight}` in its texts. */
const STAT_MS = 30_000;

// GET .../entities/resolve takes at most this many slugs (ADR 0107).
const MAX_SLUGS = 100;

const getEntity = async (tenantId: string, entityId: string) =>
  unwrap(
    await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
      params: { path: { tenant_id: tenantId, entity_id: entityId } },
    }),
  );

/** The first payload of `kind` in the entity's information of `type`, by order. */
function firstPayload<K extends Payload['kind']>(entity: Entity, type: string, kind: K) {
  return entity.information
    .filter((info) => info.type === type)
    .flatMap((info) => info.payloads)
    .find((payload): payload is Extract<Payload, { kind: K }> => payload.kind === kind);
}

// An entity's main picture as a blob: URL, fetched with the viewer's token,
// or null if it has none this viewer can see.
async function fetchPicture(tenantId: string, entityId: string): Promise<string | null> {
  try {
    const picture = firstPayload(await getEntity(tenantId, entityId), 'main_picture', 'picture');
    if (!picture) return null;
    const { data } = await client.GET('/tenants/{tenant_id}/payloads/{payload_id}/content', {
      params: { path: { tenant_id: tenantId, payload_id: picture.id } },
      parseAs: 'blob',
    });
    return data ? URL.createObjectURL(data) : null;
  } catch {
    return null;
  }
}

const isEntityReference = (ref: Reference): ref is EntityReference =>
  ref.kind === 'entity' || ref.kind === 'image';

/**
 * Renders LorenzoScript for one tenant. What each slug resolves to, and each
 * picture, is fetched once per page, slugs nothing holds included, so
 * re-rendering a live preview only asks about new ones.
 */
export function descriptionRenderer(tenantId: string, now: () => number = Date.now): Renderer {
  const slugs = new Map<string, ResolvedSlug | null>();
  // When a `my/` answer was got; plain slugs are kept for the page.
  const asked = new Map<string, number>();
  const pictures = new Map<string, Promise<string | null>>();
  // The stats of the entry a text belongs to, for its `{weight}`: by the slug of each stat's name.
  // Kept a little while, since a person edits stats and the values change under an open page.
  const statValues = new Map<
    string,
    { at: number; texts: Map<string, { name: string; text: string }> }
  >();

  async function statTexts(home: string) {
    const kept = statValues.get(home);
    if (kept && now() - kept.at < STAT_MS) return kept.texts;
    try {
      const entity = await getEntity(tenantId, home);
      const texts = new Map(
        entity.stats.map((s) => [
          slugify(s.name),
          {
            name: s.name,
            text: typeof s.value === 'boolean' ? (s.value ? 'On' : 'Off') : String(s.value),
          },
        ]),
      );
      statValues.set(home, { at: now(), texts });
      return texts;
    } catch {
      return null;
    }
  }

  /** What an answer is kept under: the slug, or for `my/` the slug with the entity it was asked for. */
  const keyOf = (ref: { hint: string; slug: string }, home: string | undefined): string =>
    ref.hint === MY ? `${home}\u0000${MY}/${ref.slug}` : ref.slug;

  const fresh = (key: string): boolean => {
    if (!slugs.has(key)) return false;
    const at = asked.get(key);
    return at === undefined || now() - at < MY_MS;
  };

  async function resolve(wanted: { ref: EntityReference; home: string | undefined }[]) {
    const plain = new Map<string, string>();
    const mine = new Map<string, Map<string, string>>();
    for (const { ref, home } of wanted) {
      const key = keyOf(ref, home);
      if (fresh(key)) continue;
      if (ref.hint !== MY) plain.set(key, ref.slug);
      else if (home !== undefined) {
        if (!mine.has(home)) mine.set(home, new Map());
        mine.get(home)?.set(key, ref.slug);
      }
    }
    const ask = async (names: string[], from?: string) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/entities/resolve', {
          params: {
            path: { tenant_id: tenantId },
            query: { slug: names, ...(from ? { from } : {}) },
          },
        }),
      );
    const keys = [...plain.keys()];
    for (let i = 0; i < keys.length; i += MAX_SLUGS) {
      const batch = keys.slice(i, i + MAX_SLUGS);
      const found = await ask(batch.map((key) => plain.get(key) as string));
      for (const key of batch) slugs.set(key, null);
      for (const entity of found) slugs.set(entity.slug, entity);
    }
    for (const [home, wantedHere] of mine) {
      const here = [...wantedHere];
      for (let i = 0; i < here.length; i += MAX_SLUGS) {
        const batch = here.slice(i, i + MAX_SLUGS);
        const found = new Map(
          (
            await ask(
              batch.map(([, slug]) => `${MY}/${slug}`),
              home,
            )
          ).map((e) => [e.slug, e]),
        );
        for (const [key, slug] of batch) {
          slugs.set(key, found.get(`${MY}/${slug}`) ?? null);
          asked.set(key, now());
        }
      }
    }
  }

  function picture(entityId: string) {
    const url = pictures.get(entityId) ?? fetchPicture(tenantId, entityId);
    pictures.set(entityId, url);
    return url;
  }

  return async (texts, homes = []) => {
    const docs = texts.map(parse);
    const refs = docs.map((doc) => references(doc).filter(isEntityReference));
    // A failed lookup is simply tried again next time; until then, its links
    // render as plain text and get no notes.
    await resolve(refs.flatMap((list, i) => list.map((ref) => ({ ref, home: homes[i] })))).catch(
      () => {},
    );
    const imageIds = refs.flatMap((list, i) =>
      list.flatMap((ref) =>
        ref.kind === 'image' ? (slugs.get(keyOf(ref, homes[i]))?.entity_id ?? []) : [],
      ),
    );
    const shown = new Map(
      await Promise.all([...new Set(imageIds)].map(async (id) => [id, await picture(id)] as const)),
    );
    const pictureOf = (entity: ResolvedSlug | null | undefined) =>
      entity ? shown.get(entity.entity_id) : undefined;

    const stats = new Map<string, Map<string, { name: string; text: string }> | null>();
    for (const [i, doc] of docs.entries()) {
      const home = homes[i];
      if (home && !stats.has(home) && statNames(doc).length) stats.set(home, await statTexts(home));
    }
    const resolverFor = (home: string | undefined): Resolver => ({
      stat: (name) => {
        const found = home ? stats.get(home)?.get(name.toLowerCase()) : undefined;
        return found ? { text: found.text, title: found.name } : null;
      },
      entity: (ref) => {
        const entity = slugs.get(keyOf(ref, home));
        const href = entity ? entityHref(tenantId, entity, ref.hint) : null;
        return entity && href ? { href, title: entity.name } : null;
      },
      image: (ref) => {
        const entity = slugs.get(keyOf(ref, home));
        const src = pictureOf(entity);
        return entity && src ? { src, title: entity.name } : null;
      },
    });
    const locale = await viewerLocales();
    return docs.map((doc, i) => ({
      html: render(doc, { resolve: resolverFor(homes[i]), locale }),
      notes: (refs[i] ?? []).flatMap((ref) => {
        const key = keyOf(ref, homes[i]);
        if (!slugs.has(key)) return [];
        const entity = slugs.get(key) ?? null;
        return linkNote(ref, entity, Boolean(pictureOf(entity))) ?? [];
      }),
    }));
  };
}

// The render each container is waiting on, so a slow one can't replace a newer one.
const pending = new WeakMap<HTMLElement, object>();

/** A text to show, with what's said about it above, such as where it's inherited from. */
export type Shown = { text: string; label?: Node | null; home?: string };

/** Shows each text as its own `.ls-content` block in `container`, its label first. */
export async function showDescriptions(
  container: HTMLElement,
  renderer: Renderer,
  shown: Shown[],
): Promise<void> {
  const turn = {};
  pending.set(container, turn);
  container.replaceChildren();
  // Links to items point into inventory-web, which the registry says where to find (ADR 0273).
  await loadAppLinks();
  const rendered = await renderer(
    shown.map(({ text }) => text),
    shown.map(({ home }) => home),
  );
  if (pending.get(container) !== turn) return;
  container.replaceChildren(
    ...rendered.flatMap(({ html }, i) => {
      const block = document.createElement('div');
      block.className = 'ls-content';
      // Safe by construction: LorenzoScript escapes every text and allows
      // only vetted URLs (ADR 0100).
      block.innerHTML = html;
      const label = shown[i]?.label;
      return label ? [label, block] : [block];
    }),
  );
}

export type Backlink = components['schemas']['BacklinkOut'];

/** The information whose descriptions link to an entity, as far as the viewer may see (ADR 0110). */
export async function getBacklinks(tenantId: string, entityId: string): Promise<Backlink[]> {
  return fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/entities/{entity_id}/backlinks', {
        params: {
          path: { tenant_id: tenantId, entity_id: entityId },
          query: { page, size: MAX_PAGE_SIZE },
        },
      }),
    ),
  );
}
