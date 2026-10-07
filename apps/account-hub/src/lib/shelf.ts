// What Shelf says about a library's repositories (RFC 0036 §3), as plain functions over what the
// API returns: the state of each repository, the outline of what it is built on, and the counts of
// what is inside. No DOM and nothing but ./types, so they run under Node in the unit tests.
// The words are those of identity.md §14.3.

import type {
  ContributionCountsOut,
  CopyPlanOut,
  CopyStepOut,
  RepositoryEntityOut,
  SubscriptionOut,
} from './types';

// The address of Shelf for a library, and of one of its repositories. `library` is the library's
// slug or id, whichever the address already had; `repository` is the repository's id.
export function shelfHref(library: string, repository?: string): string {
  const query = new URLSearchParams({ tenant: library });

  if (repository) query.set('repository', repository);

  return `/repositories/?${query.toString()}`;
}

// What an address asks for: which library and which repository, either of which may be absent.
export function readShelfLocation(search: string): {
  library: string | null;
  repository: string | null;
} {
  const query = new URLSearchParams(search);

  return { library: query.get('tenant'), repository: query.get('repository') };
}

export type ShelfState =
  | 'not-copied'
  | 'copied'
  | 'update-announced'
  | 'no-longer-offered'
  | 'not-published';

// What a library can say about one repository from the list alone. "Update announced" is all
// `published_at` against the last update can tell, so it is worded as an announcement, never as a
// count: a count needs the updates check, which runs for one repository at a time.
export function shelfState(subscription: SubscriptionOut): ShelfState {
  const { repository, granted_at, copied_at, synced_at } = subscription;

  if (granted_at === null) return 'no-longer-offered';
  if (repository.published_at === null) return 'not-published';
  if (copied_at === null) return 'not-copied';

  // Copying counts as the first update: a repository published after that has news.
  const last = Date.parse(synced_at ?? copied_at);
  const published = Date.parse(repository.published_at);

  return published > last ? 'update-announced' : 'copied';
}

export const SHELF_STATE_LABEL: Record<ShelfState, string> = {
  'not-copied': 'Not copied yet',
  copied: 'Copied',
  'update-announced': 'Update announced',
  'no-longer-offered': 'No longer offered',
  'not-published': 'Not published',
};

// One sentence for the repository's page, saying what the state means and what follows from it.
export const SHELF_STATE_EXPLANATION: Record<ShelfState, string> = {
  'not-copied': 'Your library is invited to this repository and has not copied it yet.',
  copied: 'Your library has copied this repository, and nothing newer has been announced.',
  'update-announced':
    'The repository was published after your library last updated from it. What changed is not shown here yet.',
  'no-longer-offered':
    'This repository is no longer offered to your library. What you copied stays yours, and there will be no more updates unless the owner invites your library again.',
  'not-published':
    "The repository's owner has not published it, or has unpublished it, so its contents cannot be shown. A copy your library already has stays as it is.",
};

// The classes of the brand's pills for a state. Colour only reinforces the label (§15.1).
export const SHELF_STATE_PILL: Record<ShelfState, string> = {
  'not-copied': 'pill',
  copied: 'pill pill-success',
  'update-announced': 'pill pill-warning',
  'no-longer-offered': 'pill',
  'not-published': 'pill',
};

// Repositories in the order a person reads them, those with news first.
export function sortSubscriptions(subscriptions: SubscriptionOut[]): SubscriptionOut[] {
  const rank = (s: SubscriptionOut) => (shelfState(s) === 'update-announced' ? 0 : 1);

  return [...subscriptions].sort(
    (a, b) =>
      rank(a) - rank(b) ||
      a.repository.name.localeCompare(b.repository.name, 'en', { sensitivity: 'base' }),
  );
}

// `2026-10-03T12:00:00Z` as `2026-10-03`: the day, which is all a person needs.
export function dayOf(timestamp: string): string {
  return timestamp.slice(0, 10);
}

export type OutlineState = 'this' | 'copied' | 'invited' | 'not-invited' | 'not-published';

export type OutlineNode = {
  repositoryId: string;
  name: string;
  state: OutlineState;
  label: string;
  // What to do about it, for a node the library cannot take in as it stands.
  hint: string | null;
};

const OUTLINE_LABEL: Record<OutlineState, string> = {
  this: 'This repository',
  copied: 'Copied',
  invited: 'Invited, not copied',
  'not-invited': 'Not invited',
  'not-published': 'Not published',
};

// A node of the "built on" outline from one step of the copy plan.
function outlineNode(step: CopyStepOut, state: OutlineState): OutlineNode {
  const hints: Partial<Record<OutlineState, string>> = {
    'not-invited': `Ask the owner of ${step.name} to invite your library.`,
    'not-published': `${step.name} is not published; ask its owner to publish it.`,
  };

  return {
    repositoryId: step.repository_id,
    name: step.name,
    state,
    label: OUTLINE_LABEL[state],
    hint: hints[state] ?? null,
  };
}

function stepState(step: CopyStepOut): OutlineState {
  if (step.already_copied) return 'copied';
  if (!step.granted) return 'not-invited';
  if (!step.published) return 'not-published';

  return 'invited';
}

export type Outline = {
  root: OutlineNode;
  // The repositories this one is built on, in the plan's order (the ones it needs first come
  // first). The plan lists every one a copy needs, so these are all direct: a repository that
  // builds on another has already copied that one's own dependencies (ADR 0120).
  builtOn: OutlineNode[];
};

// The outline of a repository and what it is built on, from the copy plan, which lists the
// dependencies first and the repository itself last.
export function outlineOf(plan: CopyPlanOut, repositoryId: string): Outline | null {
  const target = plan.steps.find((step) => step.repository_id === repositoryId);

  if (!target) return null;

  return {
    root: outlineNode(target, 'this'),
    builtOn: plan.steps
      .filter((step) => step.repository_id !== repositoryId)
      .map((step) => outlineNode(step, stepState(step))),
  };
}

// Whether the plan's counts mean anything. The API plans a copy only when every repository it needs
// is offered to the library and published; when one is missing it returns the plan with nothing
// counted, and a repository the library has copied is not counted again. Zero entries would then be
// a lie, so the page shows counts only when they were made, and says why when they were not.
export function countsKnown(plan: CopyPlanOut, repositoryId: string): boolean {
  const target = plan.steps.find((step) => step.repository_id === repositoryId);

  if (!target || target.already_copied) return false;

  return plan.steps.every((step) => step.already_copied || (step.granted && step.published));
}

export type InsideCount = { label: string; value: number };

// What is inside a repository, as the plan counts it: entries, stat groups, stats and the notes
// and descriptions they carry.
export function insideCounts(step: CopyStepOut): InsideCount[] {
  return [
    { label: 'Entries', value: step.entities },
    { label: 'Stat groups', value: step.stat_groups },
    { label: 'Stats', value: step.stat_definitions },
    { label: 'Descriptions and notes', value: step.information },
  ];
}

// The one sentence an attachment gets, since the interface has no noun for it: a parent that a
// repository adds to something in a repository it is built on (identity.md §14.3).
export function attachmentsSentence(count: number): string | null {
  if (count <= 0) return null;

  return count === 1
    ? 'It adds a parent to one entry of a repository it is built on.'
    : `It adds a parent to ${count} entries of repositories it is built on.`;
}

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

// What a copy brought, from the counts the list returns for a repository that was copied.
export function broughtSentence(contributed: ContributionCountsOut): string {
  const groups = contributed.stat_groups_copied + contributed.stat_groups_merged;
  const stats = contributed.stat_definitions_copied + contributed.stat_definitions_merged;

  return `It brought ${plural(contributed.entities, 'entry', 'entries')}, ${plural(groups, 'stat group', 'stat groups')} and ${plural(stats, 'stat', 'stats')}.`;
}

// A kind as a person reads it. An entry that is an item in play is an inventory item
// (identity.md §14.3).
export function kindLabel(kind: RepositoryEntityOut['kinds'][number]): string {
  switch (kind) {
    case 'item':
      return 'Item';
    case 'item_instance':
      return 'Inventory item';
    case 'being':
      return 'Being';
    case 'character':
      return 'Character';
  }
}

// An entry's parents by name, from the entries loaded so far. A parent that has not been loaded
// is counted, not named, so the line never shows an id.
export function parentsLine(
  entry: RepositoryEntityOut,
  namesById: ReadonlyMap<string, string>,
): string | null {
  if (entry.prototype_ids.length === 0) return null;

  const parts = entry.prototype_ids.flatMap((id) => {
    const name = namesById.get(id);

    return name ? [name] : [];
  });
  const unnamed = entry.prototype_ids.length - parts.length;

  if (unnamed > 0) parts.push(`${unnamed} more not shown yet`);

  return `Inherits from ${parts.join(', ')}`;
}
