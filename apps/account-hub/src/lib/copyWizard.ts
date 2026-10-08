// What the copy wizard says and decides (RFC 0036 §3, ADR 0201), as plain functions over what the
// API returns: the limits of a copy, a name clash in words and the choices for it, the choices as
// the API wants them, the receipt of a check-first copy, and the refusals a copy can meet. No DOM
// and nothing but ./types and ./apiError, so they run under Node in the unit tests. The words are
// those of identity.md §14.3.

import { ApiError } from './apiError';
import type { CollisionOut, CopyOut, CopyStepOut, PreviousCopyOut, ResolutionIn } from './types';

export type ChoiceAction = CollisionOut['choices'][number];

// What a person chose for one clash. `name` is the new name (a link name, for a link name) that
// Keep both needs, and is ignored for the other two.
export type Choice = { action: ChoiceAction; name: string };

// The limits of a copy, said before anything else. Each is true of the API as it is: a copy cannot
// be undone as a whole (ADR 0119); a library holds one game system at a time (ADR 0183); text a
// repository marks GM only comes along and stays GM only (ADR 0119).
export const COPY_LIMITS: readonly string[] = [
  'A copy cannot be undone as a whole. Your library can remove what it copied piece by piece, or copy again and replace it.',
  'A library works with one game system at a time for now, and a game system that has been copied cannot be taken out again.',
  'Notes the repository marks GM only are copied along and stay GM only: players never see them.',
  'After a copy, nothing is shared except updates, and an update never arrives by itself: you choose what to take.',
];

export const CHOICE_LABEL: Record<ChoiceAction, string> = {
  rename: 'Keep both',
  merge: 'Use the existing one',
  skip: 'Leave it out',
};

// The key a clash is known by, here and in the API: its kind and the row it comes from.
export function collisionKey(collision: Pick<CollisionOut, 'kind' | 'source_id'>): string {
  return `${collision.kind}:${collision.source_id}`;
}

// A name clash in words: what the library already has.
export function collisionSentence(collision: CollisionOut): string {
  switch (collision.kind) {
    case 'stat_group':
      return `Your library already has a stat group called “${collision.name}”.`;
    case 'stat_definition':
      return `Your library already has a stat called “${collision.name}”.`;
    case 'slug':
      return `Your library already has an entry with the link name “${collision.name}”.`;
  }
}

const THING: Record<CollisionOut['kind'], string> = {
  stat_group: 'stat group',
  stat_definition: 'stat',
  slug: 'link name',
};

// What a choice does, for the clash it is a choice for. Leaving out a stat group or a stat leaves
// out everything that uses it, and a new link name leaves the copied text's links where they were
// (ADR 0119): both are said next to the choice, not discovered afterwards.
export function choiceExplanation(collision: CollisionOut, action: ChoiceAction): string {
  switch (action) {
    case 'rename':
      return collision.kind === 'slug'
        ? 'The entry gets the new link name below. Links in the copied text that use the old one will point at your own entry, not at this one.'
        : `Your ${THING[collision.kind]} stays, and the copied one comes in under the new name below.`;
    case 'merge':
      return collision.kind === 'stat_group'
        ? 'The stats of the copied group are added to your group.'
        : 'Your own stat is used for everything that comes with the copied one. Choices it lacks are added to it.';
    case 'skip':
      switch (collision.kind) {
        case 'stat_group':
          return 'It is not copied, and nor are its stats or any value or formula that uses them.';
        case 'stat_definition':
          return 'It is not copied, and nor is any value or formula that uses it.';
        case 'slug':
          return 'The entry is copied without a link name.';
      }
  }
}

// What is recommended when a person has no reason to choose otherwise: an existing stat group or
// stat of the same name is, in nearly every case, the same thing, and where it cannot be used (a
// stat of another type) or the clash is a link name, both are kept. Leaving something out is never
// the recommendation.
export function recommendedAction(collision: CollisionOut): ChoiceAction {
  if (collision.kind !== 'slug' && collision.choices.includes('merge')) return 'merge';

  return 'rename';
}

const MAX_LINK_NAME = 100;
const LINK_NAME = /^[A-Za-z0-9][A-Za-z0-9_-]*$/;

// A name to start from for Keep both: one that shows where the copy came from.
export function suggestedName(collision: CollisionOut, repositoryName: string): string {
  if (collision.kind === 'slug') {
    return `${collision.name.slice(0, MAX_LINK_NAME - 2)}-2`;
  }

  return `${collision.name} (${repositoryName})`;
}

// The choice that is recommended for each clash.
export function recommendedChoices(
  collisions: readonly CollisionOut[],
  repositoryName: string,
): Map<string, Choice> {
  return new Map(
    collisions.map((collision) => [
      collisionKey(collision),
      { action: recommendedAction(collision), name: suggestedName(collision, repositoryName) },
    ]),
  );
}

// Why a choice cannot be sent yet, or null when it can. Only Keep both has anything to fill in.
export function choiceProblem(collision: CollisionOut, choice: Choice | undefined): string | null {
  if (!choice) return 'Choose what to do.';
  if (!collision.choices.includes(choice.action)) return 'That choice is not open for this one.';
  if (choice.action !== 'rename') return null;

  const name = choice.name.trim();

  if (name === '') {
    return collision.kind === 'slug' ? 'Type a new link name.' : 'Type a new name.';
  }

  if (collision.kind === 'slug') {
    if (!LINK_NAME.test(name) || name.length > MAX_LINK_NAME) {
      return 'A link name is letters, numbers, - and _, and starts with a letter or a number.';
    }
  }

  if (name === collision.name) return 'Type a name that is different.';

  return null;
}

// How many clashes still need something, for "3 of 7 settled".
export function unsettled(
  collisions: readonly CollisionOut[],
  choices: ReadonlyMap<string, Choice>,
): CollisionOut[] {
  return collisions.filter(
    (collision) => choiceProblem(collision, choices.get(collisionKey(collision))) !== null,
  );
}

// The choices as the API takes them: one resolution per clash.
export function resolutionsOf(
  collisions: readonly CollisionOut[],
  choices: ReadonlyMap<string, Choice>,
): ResolutionIn[] {
  return collisions.flatMap((collision) => {
    const choice = choices.get(collisionKey(collision));

    if (!choice) return [];

    return [
      {
        kind: collision.kind,
        source_id: collision.source_id,
        action: choice.action,
        ...(choice.action === 'rename' ? { name: choice.name.trim() } : {}),
      },
    ];
  });
}

// The clashes known so far with those a check just reported added. A choice can uncover another
// clash (merging a stat group makes its stats meet the library's own), so a clash the API reports
// that was not known is new, and one that was known keeps its place.
export function withFound(
  known: readonly CollisionOut[],
  found: readonly CollisionOut[],
): { all: CollisionOut[]; added: CollisionOut[] } {
  const keys = new Set(known.map(collisionKey));
  const added = found.filter((collision) => !keys.has(collisionKey(collision)));

  return { all: [...known, ...added], added };
}

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

function sum(steps: readonly CopyStepOut[], pick: (step: CopyStepOut) => number): number {
  return steps.reduce((total, step) => total + pick(step), 0);
}

// What the choices come to, as the clauses of a receipt: "use 2 existing stats", "keep both of 1",
// "leave out 1".
function tallyClauses(
  collisions: readonly CollisionOut[],
  choices: ReadonlyMap<string, Choice>,
  past: boolean,
): string[] {
  const tense = (present: string, done: string) => (past ? done : present);
  const count = { merge: { stat_group: 0, stat_definition: 0, slug: 0 }, rename: 0, skip: 0 };

  for (const collision of collisions) {
    const action = choices.get(collisionKey(collision))?.action;

    if (action === 'merge') count.merge[collision.kind] += 1;
    if (action === 'rename') count.rename += 1;
    if (action === 'skip') count.skip += 1;
  }

  const clauses: string[] = [];

  if (count.merge.stat_group > 0) {
    clauses.push(
      `${tense('use', 'used')} ${plural(count.merge.stat_group, 'existing stat group', 'existing stat groups')}`,
    );
  }

  if (count.merge.stat_definition > 0) {
    clauses.push(
      `${tense('use', 'used')} ${plural(count.merge.stat_definition, 'existing stat', 'existing stats')}`,
    );
  }

  if (count.rename > 0) clauses.push(`${tense('keep both of', 'kept both of')} ${count.rename}`);
  if (count.skip > 0) clauses.push(`${tense('leave out', 'left out')} ${count.skip}`);

  return clauses;
}

// The receipt of a copy that was only checked, or of one that was made: "Would add 309 entries, 2
// stat groups and 12 stats, use 2 existing stats and keep both of 1. Nothing has changed yet."
export function receiptSentence(
  copy: CopyOut,
  collisions: readonly CollisionOut[],
  choices: ReadonlyMap<string, Choice>,
): string {
  const past = !copy.dry_run;
  const { steps } = copy;
  const added = [
    plural(
      sum(steps, (s) => s.entities),
      'entry',
      'entries',
    ),
    plural(
      sum(steps, (s) => s.stat_groups),
      'stat group',
      'stat groups',
    ),
    plural(
      sum(steps, (s) => s.stat_definitions),
      'stat',
      'stats',
    ),
  ];
  const parts = [`${past ? 'Added' : 'Would add'} ${added[0]}, ${added[1]} and ${added[2]}`];
  const clauses = tallyClauses(collisions, choices, past);

  if (clauses.length > 0) parts.push(clauses.join(', '));

  const sentence = `${parts.join(', ')}.`;

  return past ? sentence : `${sentence} Nothing has changed yet.`;
}

// One line for each repository a copy brings in, for the list that is folded away.
export function stepLine(step: CopyStepOut): string {
  const parts = [
    plural(step.entities, 'entry', 'entries'),
    plural(step.stat_groups, 'stat group', 'stat groups'),
    plural(step.stat_definitions, 'stat', 'stats'),
    plural(step.information, 'description or note', 'descriptions and notes'),
  ];

  if (step.attachments > 0) {
    parts.push(plural(step.attachments, 'parent added to a repository below', 'parents added'));
  }

  return `${step.name}: ${parts.join(', ')}`;
}

const DROPPED_THING: Record<string, [string, string]> = {
  entity: ['entry', 'entries'],
  stat_group: ['stat group', 'stat groups'],
  stat_definition: ['stat', 'stats'],
  attachment: ['parent', 'parents'],
};

// What a copy leaves out because something it needs was not copied (usually by a choice made
// above), grouped by what and why, so a hundred entries are one sentence.
export function droppedSentences(steps: readonly CopyStepOut[]): string[] {
  const groups = new Map<string, { kind: string; reason: string; count: number }>();

  for (const step of steps) {
    for (const dropped of step.dropped) {
      const key = `${dropped.kind}:${dropped.reason}`;
      const group = groups.get(key) ?? { kind: dropped.kind, reason: dropped.reason, count: 0 };

      group.count += 1;
      groups.set(key, group);
    }
  }

  return [...groups.values()].map(({ kind, reason, count }) => {
    const [one, many] = DROPPED_THING[kind] ?? [kind.replace(/_/g, ' '), kind.replace(/_/g, ' ')];

    return `${plural(count, one, many)} left out: ${reason}.`;
  });
}

const OF_YOURS: Record<string, [string, string]> = {
  stat_definition: ['stat you added to a copied group', 'stats you added to copied groups'],
  entity_stat: ['stat value you set', 'stat values you set'],
  computed_stat: ['formula of yours', 'formulas of yours'],
  entity_stat_group: [
    'stat group you gave one of your entries',
    'stat groups you gave your entries',
  ],
  entity_prototype: ['parent you gave one of your entries', 'parents you gave your entries'],
  attachment: ['parent a repository built on it added', 'parents repositories built on it added'],
  containment: ['entry of yours held by a copied one', 'entries of yours held by copied ones'],
  ownership: ['entry a copied character owns', 'entries copied characters own'],
  group_member: ['membership of a copied group', 'memberships of copied groups'],
  knowledge: ['note one of your entries knows', 'notes your entries know'],
};

// What a purge takes of the library's own work besides the copy, from the counts a check-first
// copy returns: said in words, since the person is about to decide on them.
export function alsoRemovedSentence(also: Readonly<Record<string, number>>): string | null {
  const parts = Object.entries(also)
    .filter(([, count]) => count > 0)
    .map(([kind, count]) => {
      const [one, many] = OF_YOURS[kind] ?? [kind.replace(/_/g, ' '), kind.replace(/_/g, ' ')];

      return plural(count, one, many);
    });

  if (parts.length === 0) return null;

  return `It also removes ${parts.join(', ')}.`;
}

// What copying again does to the earlier copy, in the words of the choice.
export function previousSentence(previous: PreviousCopyOut): string {
  const earlier = [
    plural(previous.entities, 'entry', 'entries'),
    plural(previous.stat_groups, 'stat group', 'stat groups'),
    plural(previous.stat_definitions, 'stat', 'stats'),
  ].join(', ');

  if (previous.mode === 'keep') {
    return `The earlier copy stays as your own: ${earlier}. They are no longer linked to the repository, so later updates will not touch them.`;
  }

  const extra = alsoRemovedSentence(previous.also_removed);

  return `The earlier copy is removed: ${earlier}.${extra ? ` ${extra}` : ''}`;
}

export type MissingRepository = {
  repositoryId: string;
  name: string;
  granted: boolean;
  published: boolean;
};

// What a copy the API refused was refused for, in the terms the wizard acts on. A refusal that is
// none of these is shown as the API worded it.
export type CopyRefusal =
  | { kind: 'needs-choices'; collisions: CollisionOut[] }
  | { kind: 'needs-grants'; missing: MissingRepository[] }
  | { kind: 'already-copied' }
  | { kind: 'formula-cycle'; detail: string }
  | { kind: 'bad-choice'; detail: string };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function collisionOf(value: unknown): CollisionOut[] {
  if (!isRecord(value)) return [];

  const { repository_id, kind, source_id, name, local_id, choices } = value;

  if (
    typeof repository_id !== 'string' ||
    typeof source_id !== 'string' ||
    typeof name !== 'string' ||
    (kind !== 'stat_group' && kind !== 'stat_definition' && kind !== 'slug') ||
    !Array.isArray(choices)
  ) {
    return [];
  }

  return [
    {
      repository_id,
      kind,
      source_id,
      name,
      local_id: typeof local_id === 'string' ? local_id : null,
      choices: choices.filter(
        (choice): choice is ChoiceAction =>
          choice === 'rename' || choice === 'merge' || choice === 'skip',
      ),
    },
  ];
}

function missingOf(value: unknown): MissingRepository[] {
  if (!isRecord(value) || typeof value.name !== 'string') return [];

  return [
    {
      repositoryId: String(value.repository_id ?? ''),
      name: value.name,
      granted: value.granted === true,
      published: value.published === true,
    },
  ];
}

export function copyRefusal(cause: unknown): CopyRefusal | null {
  if (!(cause instanceof ApiError)) return null;

  const detail = typeof cause.problem.detail === 'string' ? cause.problem.detail : '';

  switch (cause.problemType) {
    case 'repository-copy-needs-choices': {
      const list = Array.isArray(cause.problem.collisions) ? cause.problem.collisions : [];

      return { kind: 'needs-choices', collisions: list.flatMap(collisionOf) };
    }
    case 'repository-copy-needs-grants': {
      const list = Array.isArray(cause.problem.missing) ? cause.problem.missing : [];

      return { kind: 'needs-grants', missing: list.flatMap(missingOf) };
    }
    case 'repository-already-copied':
      return { kind: 'already-copied' };
    case 'repository-copy-formula-cycle':
      return { kind: 'formula-cycle', detail };
    case 'invalid-repository-copy-choice':
      return { kind: 'bad-choice', detail };
    default:
      return null;
  }
}

// What to do about a repository a copy needs and cannot have, in a sentence.
export function missingSentence(missing: MissingRepository): string {
  return missing.granted
    ? `${missing.name} is not published; ask its owner to publish it.`
    : `Ask the owner of ${missing.name} to invite your library.`;
}

export type WizardStep = 'check' | 'clashes' | 'review' | 'done';

export const WIZARD_STEP_LABEL: Record<WizardStep, string> = {
  check: 'Check first',
  clashes: 'Name clashes',
  review: 'Review',
  done: 'Done',
};

// The steps of a copy: the clashes are a step only when there are some.
export function wizardSteps(hasClashes: boolean): WizardStep[] {
  return hasClashes ? ['check', 'clashes', 'review', 'done'] : ['check', 'review', 'done'];
}

// "Step 2 of 4: Name clashes".
export function stepHeading(step: WizardStep, hasClashes: boolean): string {
  const steps = wizardSteps(hasClashes);

  return `Step ${steps.indexOf(step) + 1} of ${steps.length}: ${WIZARD_STEP_LABEL[step]}`;
}
