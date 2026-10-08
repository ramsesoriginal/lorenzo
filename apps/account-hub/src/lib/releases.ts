// What Studio says about a repository's releases (RFC 0036 §4, RFC 0037, ADR 0209), as plain
// functions over what the API returns: the words for "matches" and "edited since", what a release
// will contain, the body of a publish, and a library's place among the releases. No DOM and nothing
// but ./types, so they run under Node in the unit tests. The words are those of identity.md §14.3.
//
// The wording rule of RFC 0037 §1: what is said is what was checked, in these words and no stronger.
// "Matches release 1.3" and "Edited since 1.3", never "stable", "frozen" or "final", and always
// beside them that text edits are not tracked.

import { dayOf } from './shelf';
import type {
  BreakingRowOut,
  PublishRequest,
  ReleaseCountsOut,
  ReleaseOut,
  ReleasePreviewOut,
  SubscriberOut,
  SubscriptionOut,
} from './types';

export const TEXT_NOT_TRACKED =
  'Text edits are not tracked: descriptions, notes and pictures are copied once, and updates do not carry them.';

export const LABEL_MAX = 80;
export const NOTES_MAX = 4000;

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

// What the repository is, checked against its latest release, in the words of the rule.
export function matchesSentence(preview: ReleasePreviewOut): string {
  const { release } = preview;

  if (release === null) return 'No release yet: it has never been published as one.';

  if (!preview.baseline || preview.matches === null) {
    return `Release ${release.label} was made before releases could be compared, so what changed since cannot be said.`;
  }

  if (preview.matches) return `Matches release ${release.label}.`;

  return `Edited since release ${release.label}: ${plural(preview.differing_rows, 'row differs', 'rows differ')}.`;
}

// The hint about text, said as one: a count that cannot see a deletion.
export function descriptionsHint(preview: ReleasePreviewOut): string | null {
  const { release, descriptions_edited: count } = preview;

  if (release === null || count === null || count === 0) return null;

  return `${plural(count, 'description', 'descriptions')} written or edited since release ${release.label}. This is a hint: a deleted description leaves no trace.`;
}

const KIND_LABEL: Record<string, [string, string]> = {
  entities: ['entry', 'entries'],
  stat_groups: ['stat group', 'stat groups'],
  stat_definitions: ['stat', 'stats'],
};

// What is in a release, or what a publish would add, as one line for each kind that has anything.
export function countsLines(counts: ReleaseCountsOut | null): string[] {
  if (counts === null) return [];

  const lines: string[] = [];

  for (const key of ['entities', 'stat_groups', 'stat_definitions'] as const) {
    const { added, changed, removed } = counts[key];
    const [, many] = KIND_LABEL[key] as [string, string];
    const parts = [
      added > 0 ? `${added} added` : null,
      changed > 0 ? `${changed} changed` : null,
      removed > 0 ? `${removed} removed` : null,
    ].filter((part): part is string => part !== null);

    if (parts.length > 0)
      lines.push(`${many.charAt(0).toUpperCase()}${many.slice(1)}: ${parts.join(', ')}.`);
  }

  const { added, removed } = counts.attachments;

  if (added > 0 || removed > 0) {
    lines.push(
      `Parents added to what other repositories hold: ${added} added, ${removed} taken off.`,
    );
  }

  return lines;
}

// The first few names of what a publish would add, change or remove, and how many more.
export function nameList(rows: readonly { name: string }[], shown = 8): string {
  const names = rows.slice(0, shown).map((row) => `“${row.name}”`);
  const more = rows.length - names.length;

  return more > 0 ? `${names.join(', ')} and ${more} more` : names.join(', ');
}

// What a publish will contain, as sentences, from a preview: nothing is made to read it.
export function contentLines(preview: ReleasePreviewOut): string[] {
  const lines = countsLines(preview.counts);

  if (preview.added.length > 0) lines.push(`New: ${nameList(preview.added)}.`);
  if (preview.removed.length > 0) lines.push(`Removed: ${nameList(preview.removed)}.`);
  if (preview.baseline && lines.length === 0)
    lines.push('Nothing differs from the latest release.');

  return lines;
}

// What a publish will break, each as the API says it in words, with what it is about.
export function breakingLines(rows: readonly BreakingRowOut[]): string[] {
  return rows.map((row) => row.detail);
}

// What a publish only says: parents added to items libraries may already hold. Never refused, and
// nothing to acknowledge; the library names each one before it takes it. The first few are named.
export const WARNING_TITLE = 'Parents added to items libraries may already hold';
const WARNING_SHOWN = 8;

export function warningLines(rows: readonly BreakingRowOut[]): string[] {
  if (rows.length === 0) return [];

  const more = rows.length - WARNING_SHOWN;
  const lines = rows.slice(0, WARNING_SHOWN).map((row) => row.detail);

  if (more > 0) lines.push(`and ${more} more.`);

  return [
    `${rows.length === 1 ? 'A parent is' : `${rows.length} parents are`} added to items libraries may already hold. Each changes what its item is in a library that holds it, and a library chooses each one before it takes it. This does not make the release breaking.`,
    ...lines,
  ];
}

export const ACKNOWLEDGE_TEXT =
  'I understand that these changes break libraries that already copied this repository, and publish them anyway.';

export type ComposerForm = {
  label: string;
  notes: string;
  breaking: boolean;
  acknowledged: boolean;
};

// Why the form cannot be sent yet, or null. A label is free text and may be left blank (it is then
// the release's number); a breaking change must be acknowledged.
export function composerProblem(
  form: ComposerForm,
  hits: readonly BreakingRowOut[],
): string | null {
  if (form.label.trim().length > LABEL_MAX) return `A label is at most ${LABEL_MAX} characters.`;
  if (form.notes.trim().length > NOTES_MAX) return `Notes are at most ${NOTES_MAX} characters.`;
  if (hits.length > 0 && !form.acknowledged) {
    return 'This release breaks things. Say you understand, to publish it.';
  }

  return null;
}

// The body of a publish, from the form: what is left blank is left out, so the API's defaults apply.
export function publishBody(form: ComposerForm, hits: readonly BreakingRowOut[]): PublishRequest {
  return {
    ...(form.label.trim() ? { label: form.label.trim() } : {}),
    ...(form.notes.trim() ? { notes: form.notes.trim() } : {}),
    breaking: form.breaking || (hits.length > 0 && form.acknowledged),
    acknowledge_breaking: hits.length > 0 && form.acknowledged,
  };
}

// What a label will be if the author writes none: the next number.
export function defaultLabel(preview: ReleasePreviewOut | null): string {
  return String((preview?.release?.number ?? 0) + 1);
}

export function releaseDate(release: Pick<ReleaseOut, 'created_at'>): string {
  return dayOf(release.created_at);
}

// A library's place among the releases, from the list of repositories: which release it last took
// and whether there is a later one. Null where the repository has no release or the library has
// not copied it.
export function releasePlace(
  subscription: Pick<SubscriptionOut, 'synced_release' | 'current_release' | 'copied_at'>,
): { took: string | null; latest: string; behind: boolean } | null {
  const { synced_release: took, current_release: latest } = subscription;

  if (subscription.copied_at === null || latest === null) return null;

  return {
    took: took?.label ?? null,
    latest: latest.label,
    behind: took === null || took.id !== latest.id,
  };
}

// The same for the owner's list of who uses it: which release a library is on.
export function onRelease(row: Pick<SubscriberOut, 'synced_release' | 'copied_at'>): string | null {
  if (row.copied_at === null) return null;

  return row.synced_release ? `on release ${row.synced_release.label}` : null;
}

export const RELEASES_NOTE =
  'A release is what you said the repository was when you published it: a label, notes, and whether it breaks things. Libraries read the repository as it is, not a copy of the release.';
