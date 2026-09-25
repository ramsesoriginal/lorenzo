// Where a LorenzoScript link to an entity leads in this app, and what an
// author should know about links readers can't follow (ADR 0108). Pure, so
// it's tested without a browser; descriptions.ts does the fetching.
import type { EntityRef, Reference } from '@lorenzo/lorenzoscript';
import type { components } from './api';

export type ResolvedSlug = components['schemas']['ResolvedSlugOut'];
/** A link or picture naming an entity by slug. */
export type EntityReference = Extract<Reference, EntityRef>;
type Kind = ResolvedSlug['kinds'][number];

type View = { kind: Kind; page: string; href: (tenantId: string, entityId: string) => string };
const itemPage: View['href'] = (t, id) => `/item/?tenant=${t}&id=${id}`;
const board: View['href'] = (t, id) => `/board/?tenant=${t}&character=${id}`;

// The pages an entity can open in, in the order a link without a usable
// hint tries them. A plain being has none here.
const VIEWS: View[] = [
  { kind: 'item_instance', page: 'its item page', href: itemPage },
  { kind: 'item', page: 'its item page', href: itemPage },
  { kind: 'character', page: 'the board', href: board },
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
  if (!entity) return `No entity has the slug “${ref.slug}” yet, so readers see ${fallback}.`;
  if (ref.kind === 'image') {
    return hasPicture ? null : `${entity.name} has no picture, so readers see the alt text.`;
  }
  const view = viewFor(entity, ref.hint);
  const mismatch = ref.hint !== '' && !entity.kinds.includes(ref.hint as Kind);
  const hint = ref.hint.replace(/_/g, ' ');
  const what = `${entity.name} isn't ${/^[aeiou]/.test(hint) ? 'an' : 'a'} ${hint}`;
  if (!view) {
    return mismatch
      ? `${what} and has no page here, so readers see plain text.`
      : `${entity.name} has no page here, so readers see plain text.`;
  }
  return mismatch ? `${what}; the link opens ${view.page} instead.` : null;
}
