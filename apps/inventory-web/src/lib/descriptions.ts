// Descriptions as LorenzoScript (RFC 0027, ADR 0108): rendering them with
// this tenant's entities resolved, and what links to an entity. Writing
// them is information.ts's.
import { parse, type Reference, type Resolver, references, render } from '@lorenzo/lorenzoscript';
import { client, type components, fetchAllPages, MAX_PAGE_SIZE, unwrap } from './api';
import { type EntityReference, entityHref, linkNote, type ResolvedSlug } from './entityLinks';
import { viewerLocales } from './me';

type Entity = components['schemas']['EntityDetailOut'];
type Payload = Entity['information'][number]['payloads'][number];

/** One text's HTML, and what an author should know about links in it that won't work. */
export type Rendered = { html: string; notes: string[] };
export type Renderer = (texts: string[]) => Promise<Rendered[]>;

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
export function descriptionRenderer(tenantId: string): Renderer {
  const slugs = new Map<string, ResolvedSlug | null>();
  const pictures = new Map<string, Promise<string | null>>();

  async function resolve(wanted: string[]) {
    const missing = [...new Set(wanted)].filter((slug) => !slugs.has(slug));
    for (let i = 0; i < missing.length; i += MAX_SLUGS) {
      const batch = missing.slice(i, i + MAX_SLUGS);
      const found = await unwrap(
        await client.GET('/tenants/{tenant_id}/entities/resolve', {
          params: { path: { tenant_id: tenantId }, query: { slug: batch } },
        }),
      );
      for (const slug of batch) slugs.set(slug, null);
      for (const entity of found) slugs.set(entity.slug, entity);
    }
  }

  function picture(entityId: string) {
    const url = pictures.get(entityId) ?? fetchPicture(tenantId, entityId);
    pictures.set(entityId, url);
    return url;
  }

  return async (texts) => {
    const docs = texts.map(parse);
    const refs = docs.map((doc) => references(doc).filter(isEntityReference));
    // A failed lookup is simply tried again next time; until then, its links
    // render as plain text and get no notes.
    await resolve(refs.flat().map((ref) => ref.slug)).catch(() => {});
    const imageIds = refs
      .flat()
      .flatMap((ref) => (ref.kind === 'image' ? (slugs.get(ref.slug)?.entity_id ?? []) : []));
    const shown = new Map(
      await Promise.all([...new Set(imageIds)].map(async (id) => [id, await picture(id)] as const)),
    );
    const pictureOf = (entity: ResolvedSlug | null | undefined) =>
      entity ? shown.get(entity.entity_id) : undefined;

    const resolver: Resolver = {
      entity: ({ hint, slug }) => {
        const entity = slugs.get(slug);
        const href = entity ? entityHref(tenantId, entity, hint) : null;
        return entity && href ? { href, title: entity.name } : null;
      },
      image: ({ slug }) => {
        const entity = slugs.get(slug);
        const src = pictureOf(entity);
        return entity && src ? { src, title: entity.name } : null;
      },
    };
    const options = { resolve: resolver, locale: await viewerLocales() };
    return docs.map((doc, i) => ({
      html: render(doc, options),
      notes: (refs[i] ?? []).flatMap((ref) => {
        if (!slugs.has(ref.slug)) return [];
        const entity = slugs.get(ref.slug) ?? null;
        return linkNote(ref, entity, Boolean(pictureOf(entity))) ?? [];
      }),
    }));
  };
}

// The render each container is waiting on, so a slow one can't replace a newer one.
const pending = new WeakMap<HTMLElement, object>();

/** A text to show, with what's said about it above, such as where it's inherited from. */
export type Shown = { text: string; label?: Node | null };

/** Shows each text as its own `.ls-content` block in `container`, its label first. */
export async function showDescriptions(
  container: HTMLElement,
  renderer: Renderer,
  shown: Shown[],
): Promise<void> {
  const turn = {};
  pending.set(container, turn);
  container.replaceChildren();
  const rendered = await renderer(shown.map(({ text }) => text));
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
