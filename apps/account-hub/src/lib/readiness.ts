// "Before this can be public": what a private repository still lacks, beside the visibility card on
// Studio's Overview (RFC 0038 §2, RFC 0036 §4 T7, ADR 0385), as plain functions over what the API
// returns. It is only a list: what the flip requires is ADR 0289's and 0290's and stands as it is, and
// the Make public dialog asks the API again before it does anything. No DOM and nothing but
// ./visibility and ./types, so they run under Node in the unit tests. The words are those of
// identity.md §14.3.

import type { FlipCheckOut } from './types';
import { publicBlockers } from './visibility';

export const READINESS_HEADING = 'Before this can be public';
export const READINESS_NOTE =
  'This only tells you what is missing. The Make public dialog checks it again before it changes anything.';

// Where a link goes: a field of the Profile tab, the Built on tab, or another repository's Studio page.
export type ReadinessTarget =
  | { kind: 'summary' }
  | { kind: 'cover' }
  | { kind: 'built-on' }
  | { kind: 'page'; href: string };

export type ReadinessItem = {
  // Whether the flip asks for it (a summary, what it is built on) or it is only a good idea (a cover).
  need: 'required' | 'recommended';
  done: boolean;
  text: string;
  link: { label: string; target: ReadinessTarget } | null;
};

// The list, from what the flip check read and whether the profile has a cover.
export function readinessOf(
  check: Pick<FlipCheckOut, 'has_summary' | 'built_on_not_public' | 'built_on_behind'>,
  hasCover: boolean,
): ReadinessItem[] {
  const items: ReadinessItem[] = [
    check.has_summary
      ? { need: 'required', done: true, text: 'It has a summary.', link: null }
      : {
          need: 'required',
          done: false,
          text: 'It needs a summary. A repository cannot be made public without one.',
          link: { label: 'Write the summary', target: { kind: 'summary' } },
        },
    hasCover
      ? { need: 'recommended', done: true, text: 'It has a cover.', link: null }
      : {
          need: 'recommended',
          done: false,
          text: 'A cover is not required, but it is the first thing people see.',
          link: { label: 'Add a cover', target: { kind: 'cover' } },
        },
  ];

  const blockers = publicBlockers(check);

  if (blockers.length === 0) {
    items.push({
      need: 'required',
      done: true,
      text: 'Everything it is built on is public and up to date.',
      link: null,
    });

    return items;
  }

  for (const blocker of blockers) {
    items.push({
      need: 'required',
      done: false,
      text: blocker.text,
      link: blocker.link
        ? { label: blocker.link.label, target: { kind: 'page', href: blocker.link.href } }
        : { label: 'Open Built on', target: { kind: 'built-on' } },
    });
  }

  return items;
}

// Whether the list is shown at all: a private repository that its Owner may make public here. A public
// one needs no check, and a deployment that accepts no public repository has nothing to prepare for.
export function showsReadiness(
  check: Pick<FlipCheckOut, 'visibility' | 'available'> | null,
  role: string,
): boolean {
  return role === 'owner' && check !== null && check.available && check.visibility === 'private';
}

// How many of the items the flip asks for are still open: "2 things to do".
export function openRequired(items: readonly ReadinessItem[]): number {
  return items.filter((item) => item.need === 'required' && !item.done).length;
}
