// Where a LorenzoScript link to an entity leads in this app, and what an
// author should know about links readers can't follow (ADR 0108). Pure, so
// it's tested without a browser; descriptions.ts does the fetching.
import type { EntityRef, Reference } from '@lorenzo/lorenzoscript';
import type { components } from './api';
import { INVENTORY_WEB_BASE_URL } from './config';

export type ResolvedSlug = components['schemas']['ResolvedSlugOut'];
/** A link or picture naming an entity by slug. */
export type EntityReference = Extract<Reference, EntityRef>;
type Kind = ResolvedSlug['kinds'][number];

type View = { kind: Kind; page: string; href: (tenantId: string, entityId: string) => string };

/** A being's own page here, named by its slug when it has one, else by its id (ADR 0135). */
export function beingPageHref(
  tenant: string,
  being: { entity_id: string; slug?: string | null },
): string {
  const named = being.slug ? `slug=${encodeURIComponent(being.slug)}` : `id=${being.entity_id}`;

  return `/being/?tenant=${encodeURIComponent(tenant)}&${named}`;
}

/** A being's board in inventory-web, or null if this deployment does not know where that is. */
export function inventoryBoardHref(tenant: string, entityId: string): string | null {
  return INVENTORY_WEB_BASE_URL
    ? `${INVENTORY_WEB_BASE_URL}/board/?tenant=${encodeURIComponent(tenant)}&character=${entityId}`
    : null;
}

const beingPage: View['href'] = (t, id) => beingPageHref(t, { entity_id: id });
// An item has no page here: inventory-web has, when it is configured (ADR 0270).
const itemPage: View['href'] = (t, id) =>
  `${INVENTORY_WEB_BASE_URL}/item/?tenant=${encodeURIComponent(t)}&id=${id}`;

// The pages an entity can open in, in the order a link without a usable hint tries them.
const VIEWS: View[] = [
  { kind: 'character', page: 'its page', href: beingPage },
  { kind: 'being', page: 'its page', href: beingPage },
  ...(INVENTORY_WEB_BASE_URL
    ? ([
        { kind: 'item_instance', page: 'its item page in Inventory', href: itemPage },
        { kind: 'item', page: 'its item page in Inventory', href: itemPage },
      ] as View[])
    : []),
];

/** What choosing a page needs to know about an entity: a resolved slug, or a backlink. */
type Linkable = Pick<ResolvedSlug, 'entity_id' | 'kinds'>;

// The hint's view if the entity is one, else the entity's first kind with a view.
function viewFor(entity: Linkable, hint: string) {
  const views = VIEWS.filter(({ kind }) => entity.kinds.includes(kind));
  return views.find(({ kind }) => kind === hint) ?? views[0];
}

/** Where a link to `entity` leads, or null if it has no page here. */
export function entityHref(tenantId: string, entity: Linkable, hint = ''): string | null {
  return viewFor(entity, hint)?.href(tenantId, entity.entity_id) ?? null;
}

/**
 * Why readers won't be able to follow `ref`, or null if they will. `entity`
 * is what its slug resolved to (null: nothing holds it); `hasPicture` says
 * whether that entity has a main picture this viewer can see.
 */
export function linkNote(
  ref: EntityReference,
  entity: ResolvedSlug | null,
  hasPicture: boolean,
): string | null {
  const fallback = ref.kind === 'image' ? 'the alt text' : 'plain text';
  if (!entity) {
    return ref.hint === 'my'
      ? `Nothing called “${ref.slug}” is held by whoever this belongs to, so readers see ${fallback}.`
      : `No entity has the slug “${ref.slug}” yet, so readers see ${fallback}.`;
  }
  if (ref.kind === 'image') {
    return hasPicture ? null : `${entity.name} has no picture, so readers see the alt text.`;
  }
  const view = viewFor(entity, ref.hint);
  const mismatch = ref.hint !== '' && ref.hint !== 'my' && !entity.kinds.includes(ref.hint as Kind);
  const hint = ref.hint.replace(/_/g, ' ');
  const what = `${entity.name} isn't ${/^[aeiou]/.test(hint) ? 'an' : 'a'} ${hint}`;
  if (!view) {
    return mismatch
      ? `${what} and has no page here, so readers see plain text.`
      : `${entity.name} has no page here, so readers see plain text.`;
  }
  return mismatch ? `${what}; the link opens ${view.page} instead.` : null;
}
