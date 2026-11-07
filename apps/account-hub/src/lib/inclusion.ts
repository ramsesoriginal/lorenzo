// What Studio says about how a repository carries one it is built on, and about what repositories built
// on it may do with it (RFC 0051 H1, ADR 0431), as plain functions over what the API returns: the
// words of the choice, what each choice does, why one is not offered, the note on changing it, the
// terms card, the lines of a storefront that includes something, and the lines of a release that
// would be breaking because of it. No DOM and nothing but ./types and ./discover, so they run under
// Node in the unit tests.
//
// The words are those of the RFC's table and identity.md §14.3: library, repository, release, Owner,
// entry, copy, update, "built on". The screens never say tenant, grant, subscription, flatten or
// source.

import { licenceLine, NO_LICENCE } from './discover';
import type {
  BuiltOnSourceOut,
  IncludableOut,
  IncludedSourceOut,
  InclusionChangeOut,
  InclusionOut,
  SubscriptionOut,
  TermsOut,
} from './types';

export type Inclusion = InclusionOut['inclusion'];

// ---------------------------------------------------------------------------------------------
// The choice, for each repository a repository is built on.

export const INCLUSION_LEGEND = 'How is it carried in this repository?';

export const INCLUSION_LABEL: Record<Inclusion, string> = {
  show: 'Keep separate and visible',
  include: 'Include in this repository',
};

export const INCLUSION_CHOICES: readonly Inclusion[] = ['show', 'include'];

// The choices to offer: "Include in this repository" only where the user may include it. What is already
// chosen stays offered, so that it shows as chosen even where it could not be chosen again.
export function offeredChoices(
  includable: Pick<IncludableOut, 'allowed'> | null | undefined,
  current: Inclusion,
): Inclusion[] {
  return INCLUSION_CHOICES.filter(
    (choice) => choice !== 'include' || includable?.allowed === true || current === choice,
  );
}

// What each choice does, said before it is chosen: for a library that copies this repository, and for
// this repository's own Owner.
export function inclusionEffect(choice: Inclusion, name: string): string {
  return choice === 'include'
    ? `The entries of ${name} become this repository’s own when you publish a release. A library that copies this repository does not need ${name} and never reads it. Your copy of ${name} here is not changed, and you keep taking its updates.`
    : `${name} stays a repository of its own. A library that copies this repository is given ${name} too, so it has to be one the library can read.`;
}

// Why "Include in this repository" is not offered, or null where it is. Only the Owner of a repository
// can say yes to it being included elsewhere: an Owner of it, or the choice it made for repositories
// built on it.
export function notOfferedReason(
  name: string,
  includable: Pick<IncludableOut, 'allowed'> | null | undefined,
): string | null {
  if (includable?.allowed !== false) return null;

  return `You cannot include ${name} here: its Owner has not allowed repositories built on it to include it, and you are not one of its Owners. Ask its Owner to turn on “${TERMS_INCLUDE_LABEL}”, or keep it separate.`;
}

// After the repository's first public release a choice made again makes the next release breaking: the
// rows libraries hold change where they come from. Said beside the choice once a release carried it.
export const BREAKING_NOTE = 'Changing how this is included makes a breaking release.';

export function breakingNote(
  row: Partial<Pick<SubscriptionOut, 'inclusion_in_release'>> &
    Partial<Pick<BuiltOnSourceOut, 'in_release'>>,
): string | null {
  const carried = row.inclusion_in_release ?? row.in_release;

  return carried === null || carried === undefined ? null : BREAKING_NOTE;
}

// What is said once a choice was changed: whether the next release is breaking for it.
export function inclusionSaved(answer: InclusionOut): string {
  return answer.breaking_next_release
    ? `Saved. ${BREAKING_NOTE} You will be asked to acknowledge it when you publish.`
    : 'Saved.';
}

// ---------------------------------------------------------------------------------------------
// A repository's terms: what repositories built on it may do with it.

export const TERMS_HEADING = 'How repositories built on this one may use it';
export const TERMS_INTRO =
  'You decide whether a repository built on this one may carry it in its own release. Nobody else can say yes for you.';
export const TERMS_INCLUDE_LABEL = 'May be included';
export const TERMS_INCLUDE_HELP =
  'A repository built on this one may include it: its entries become that repository’s own, and a library that copies that repository never reads this one.';

// What the switch says now, from what the API reports, in a sentence under it: who chose, and what
// it follows when nobody did.
export function termsLine(terms: Pick<TermsOut, 'may_be_included' | 'is_default'>): string {
  if (!terms.is_default) {
    return terms.may_be_included
      ? 'You allowed it. Repositories built on this one may include it.'
      : 'You did not allow it. Only an Owner of this repository can include it in another.';
  }

  return terms.may_be_included
    ? 'Nobody chose: a public repository may be included, since anyone can copy it. Turn the switch off to say otherwise.'
    : 'Nobody chose: a private repository may not be included, except by its own Owners. Turn the switch on to allow it.';
}

export function termsPatch(on: boolean): { terms: { may_be_included: boolean } } {
  return { terms: { may_be_included: on } };
}

export const TERMS_SAVING = 'Saving…';
export const TERMS_SAVED = 'Saved.';

// ---------------------------------------------------------------------------------------------
// What a storefront says of a repository that includes another.

export type IncludesLine = { text: string; name: string; licence: string; url: string | null };

// “Includes content from Armoury, CC BY 4.0”: the name and the licence as they were when the release
// was made, and “no licence stated” where there was none.
export function includesLine(source: IncludedSourceOut): IncludesLine {
  const licence = licenceLine(source.licence);
  const said = licence.text === NO_LICENCE ? 'no licence stated' : licence.text;

  return {
    text: `Includes content from ${source.name}, ${said}`,
    name: source.name,
    licence: said,
    url: licence.url,
  };
}

export function includesLines(sources: readonly IncludedSourceOut[] | undefined): IncludesLine[] {
  return (sources ?? []).map(includesLine);
}

// The same as facts of the profile preview in Studio: the term and the value, with the licence's link.
export function includesFacts(
  sources: readonly IncludedSourceOut[] | undefined,
): { term: string; value: string; url: string | null }[] {
  return includesLines(sources).map((line) => ({
    term: 'Includes content from',
    value: `${line.name}, ${line.licence}`,
    url: line.url,
  }));
}

// ---------------------------------------------------------------------------------------------
// A release that is breaking for how it carries something, in the release composer.

export function inclusionChangeLine(change: Pick<InclusionChangeOut, 'name' | 'before' | 'after'>) {
  return change.after === 'include'
    ? `“${change.name}” was kept separate in the last public release and is included now. A library that holds this repository gets its entries as this repository’s own, which changes them there.`
    : `“${change.name}” was included in the last public release and is kept separate now. Its entries leave this repository, and a library that holds it needs ${change.name} as a repository of its own.`;
}

export function inclusionChangeLines(changes: readonly InclusionChangeOut[] | undefined): string[] {
  return (changes ?? []).map(inclusionChangeLine);
}

// The API's refusal of a release lists them in its problem; read what it carries, or nothing.
export function inclusionChangesOf(problem: Record<string, unknown>): InclusionChangeOut[] {
  const changes = problem.inclusion_changes;

  if (!Array.isArray(changes)) return [];

  return changes.filter(
    (change): change is InclusionChangeOut =>
      typeof change === 'object' &&
      change !== null &&
      typeof (change as InclusionChangeOut).name === 'string' &&
      ['show', 'include'].includes((change as InclusionChangeOut).after),
  );
}

// ---------------------------------------------------------------------------------------------
// The built-on list of the "Make public" dialog.

export const BUILT_ON_CHOICES_TITLE = 'How this repository carries what it is built on';

// A repository this one is built on, as the dialog offers its choice: what it is, what is chosen, and
// why "Include in this repository" is not offered, where it is not.
export type BuiltOnChoice = {
  id: string;
  name: string;
  state: string;
  inclusion: Inclusion;
  offered: readonly Inclusion[];
  notOffered: string | null;
  effect: string;
  note: string | null;
};

export function builtOnChoices(sources: readonly BuiltOnSourceOut[] | undefined): BuiltOnChoice[] {
  return (sources ?? []).map((source) => {
    const notOffered = notOfferedReason(source.name, source.includable);
    const offered = offeredChoices(source.includable, source.inclusion);

    return {
      id: source.id,
      name: source.name,
      state: source.public ? 'Public' : 'Private',
      inclusion: source.inclusion,
      offered,
      notOffered,
      effect: inclusionEffect(source.inclusion, source.name),
      note: breakingNote(source),
    };
  });
}
