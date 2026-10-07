// What Shelf's update inbox says and decides (RFC 0036 §3, ADR 0203), as plain functions over what
// the API returns: a field's change in words ("Was / Now / Yours"), the groups a library's updates
// fall into, which rows "apply all clean" takes, the actions as the API wants them, and what an
// apply did. No DOM and nothing but ./types, so they run under Node in the unit tests. The words
// are those of identity.md §14.3.

import type {
  AddedOut,
  ApplyUpdatesOut,
  AttachmentActionIn,
  AttachmentAddedOut,
  AttachmentRefOut,
  FieldChangeOut,
  NotAppliedOut,
  RowChangeOut,
  RowRefOut,
  UpdateActionIn,
  UpdatesOut,
} from './types';

// Said once at the top of every repository's updates: what the comparison leaves out (ADR 0121), so
// that a fixed typo that does not arrive is not a surprise.
export const NOT_COMPARED_NOTE =
  'Descriptions and notes, where things are held and who owns them are copied once and never updated, so a change to one of those does not arrive here.';

// Said once, where applying is: an update changes the library, and so what its players see.
export const PLAYERS_NOTE = 'Applying an update changes what your players see.';

// Updates never apply by themselves, and this is where that is said.
export const NEVER_BY_ITSELF = 'Nothing is applied until you apply it.';

export type RowKindName = RowChangeOut['kind'];

export const ROW_KIND_LABEL: Record<RowKindName, string> = {
  entity: 'Entry',
  stat_group: 'Stat group',
  stat_definition: 'Stat',
};

// The key a row is known by in the page: its kind and the repository's row.
export function rowKey(row: { kind: string; source_id: string }): string {
  return `${row.kind}:${row.source_id}`;
}

// --- Names ---------------------------------------------------------------------------------------

export type Names = Readonly<Record<string, string>>;
export type Thing = 'entry' | 'stat group' | 'stat';

// An id as a person reads it: the name the API gave, or a word for what has none. An id the
// library's links no longer know is not in `names`, and is said as what it was, never shown (ADR
// 0197).
export function nameOrWord(names: Names, id: unknown, thing: Thing): string {
  if (typeof id !== 'string' || id === '') return '(none)';

  const name = names[id];

  if (name !== undefined && name !== '') return name;

  return `${thing === 'entry' ? 'an' : 'a'} ${thing} that is gone`;
}

// --- Values and fields ---------------------------------------------------------------------------

const ROUNDING: Record<string, string> = {
  floor: 'rounded down',
  ceil: 'rounded up',
  round: 'rounded to the nearest',
  truncate: 'cut toward zero',
};

const COMPARATOR: Record<string, string> = {
  lt: 'is less than',
  le: 'is at most',
  eq: 'is',
  ne: 'is not',
  ge: 'is at least',
  gt: 'is more than',
};

// "1.0000" as "1": a decimal as it was written in a formula, without the zeros the database added.
function number(text: unknown): string {
  const value = Number(text);

  return Number.isFinite(value) ? String(value) : String(text);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function signed(offset: unknown): string {
  const value = Number(offset);

  if (!Number.isFinite(value) || value === 0) return '';

  return value < 0 ? ` − ${number(Math.abs(value))}` : ` + ${number(value)}`;
}

function rounding(mode: unknown): string {
  return typeof mode === 'string' && ROUNDING[mode] ? `, ${ROUNDING[mode]}` : '';
}

// A formula in words: what a stat is worked out from.
export function formulaText(formula: unknown, names: Names): string {
  if (!isRecord(formula)) return '(none)';

  const stat = (id: unknown) => nameOrWord(names, id, 'stat');

  switch (formula.kind) {
    case 'linear':
      return `${stat(formula.source)} × ${number(formula.multiplier)}${signed(formula.offset)}${rounding(formula.round_mode)}`;
    case 'sum': {
      const terms = Array.isArray(formula.terms) ? formula.terms : [];
      const parts = terms.map((term) =>
        isRecord(term) ? `${number(term.coefficient)} × ${stat(term.source)}` : '',
      );

      return `${parts.join(' + ') || '0'}${signed(formula.offset)}${rounding(formula.round_mode)}`;
    }
    case 'contents':
      return `the total of ${stat(formula.source)} in what it holds`;
    case 'comparison': {
      const comparator = COMPARATOR[String(formula.comparator)] ?? String(formula.comparator);
      const right = formula.right ? stat(formula.right) : number(formula.right_constant);

      return `${stat(formula.left)} ${comparator} ${right}: ${formula.true_value ?? ''}, otherwise ${formula.false_value ?? ''}`;
    }
    default:
      return '(none)';
  }
}

export type Reading =
  | { type: 'text' | 'number' | 'bool' | 'plain' }
  | { type: 'ref'; thing: Thing }
  | { type: 'formula' }
  | { type: 'set'; thing: Thing | null };

export type FieldInfo = { label: string; reading: Reading };

const WORDS: Record<string, FieldInfo> = {
  name: { label: 'Name', reading: { type: 'text' } },
  in_public_catalog: { label: 'In the public catalog', reading: { type: 'bool' } },
  slug: { label: 'Link name', reading: { type: 'text' } },
  prototypes: { label: 'Inherits from', reading: { type: 'set', thing: 'entry' } },
  stat_groups: { label: 'Stat groups', reading: { type: 'set', thing: 'stat group' } },
  priority: { label: 'Priority', reading: { type: 'number' } },
  mandatory: { label: 'Mandatory', reading: { type: 'bool' } },
  value_type: { label: 'Value type', reading: { type: 'plain' } },
  stat_group: { label: 'Stat group', reading: { type: 'ref', thing: 'stat group' } },
  enum_values: { label: 'Choices', reading: { type: 'set', thing: null } },
};

function titleCase(field: string): string {
  const words = field.replace(/_/g, ' ');

  return words.charAt(0).toUpperCase() + words.slice(1);
}

// What a field is called and how its values read. A stat's value or formula is `stats:<id>` or
// `formulas:<id>`, named by the label the API gives (and by `names` where it does not).
export function fieldInfo(
  change: Pick<FieldChangeOut, 'field' | 'label'>,
  names: Names,
): FieldInfo {
  const [head, id] = change.field.split(':', 2);
  const known = WORDS[change.field];

  if (known) return known;

  if (head === 'stats' || head === 'formulas') {
    const label = change.label ?? (id ? nameOrWord(names, id, 'stat') : 'a stat');

    return head === 'stats'
      ? { label: `Stat: ${label}`, reading: { type: 'plain' } }
      : { label: `Formula: ${label}`, reading: { type: 'formula' } };
  }

  return { label: titleCase(change.field), reading: { type: 'plain' } };
}

// One value, read for the field it belongs to.
export function valueText(reading: Reading, value: unknown, names: Names): string {
  if (value === null || value === undefined || value === '') return '(none)';

  switch (reading.type) {
    case 'bool':
      return value === true ? 'yes' : value === false ? 'no' : String(value);
    case 'ref':
      return nameOrWord(names, value, reading.thing);
    case 'formula':
      return formulaText(value, names);
    case 'set':
      return reading.thing === null ? String(value) : nameOrWord(names, value, reading.thing);
    default:
      if (typeof value === 'boolean') return value ? 'yes' : 'no';
      if (typeof value === 'object') return JSON.stringify(value);

      return String(value);
  }
}

export type FieldView = {
  field: string;
  label: string;
  state: FieldChangeOut['state'];
  // For a field with one value: what it was when the library last updated, what it is upstream
  // now, and, where the library changed it too, what the library has.
  was: string | null;
  now: string | null;
  yours: string | null;
  // For a set (what it inherits from, its stat groups, its choices): what upstream added and took
  // away.
  added: string[] | null;
  removed: string[] | null;
  // Why a field cannot be applied.
  note: string | null;
};

const VALUE_TYPE_NOTE =
  'The type of this stat changed upstream. It cannot be applied, because every value would have to be converted: change it by hand.';

// A changed field in words.
export function describeField(change: FieldChangeOut, names: Names): FieldView {
  const { label, reading } = fieldInfo(change, names);
  const base: FieldView = {
    field: change.field,
    label,
    state: change.state,
    was: null,
    now: null,
    yours: null,
    added: null,
    removed: null,
    note: change.state === 'not_applicable' ? VALUE_TYPE_NOTE : null,
  };

  if (reading.type === 'set') {
    const items = (list: readonly unknown[] | null) =>
      (list ?? []).map((value) => valueText(reading, value, names));

    return { ...base, added: items(change.added), removed: items(change.removed) };
  }

  return {
    ...base,
    was: valueText(reading, change.base, names),
    now: valueText(reading, change.upstream, names),
    yours: change.state === 'conflict' ? valueText(reading, change.local, names) : null,
  };
}

export type RowView = {
  key: string;
  kind: RowKindName;
  kindLabel: string;
  name: string;
  sourceId: string;
  fields: FieldView[];
  // What the library changed too, which it has to choose about one by one.
  conflicts: FieldView[];
  // Whether there is anything in the row to apply: a row with only a changed value type has not.
  appliable: boolean;
};

export function describeRow(row: RowChangeOut, names: Names): RowView {
  const fields = row.fields.map((field) => describeField(field, names));

  return {
    key: rowKey(row),
    kind: row.kind,
    kindLabel: ROW_KIND_LABEL[row.kind],
    name: row.name,
    sourceId: row.source_id,
    fields,
    conflicts: fields.filter((field) => field.state === 'conflict'),
    appliable: fields.some((field) => field.state !== 'not_applicable'),
  };
}

// --- Groups and counts ---------------------------------------------------------------------------

export type UpdateGroups = {
  added: AddedOut[];
  // Changed rows the library has no edit in.
  changed: RowChangeOut[];
  // Changed rows the library changed too: at least one field is a conflict.
  conflicts: RowChangeOut[];
  removed: RowRefOut[];
  deletedLocally: RowRefOut[];
  attachmentsAdded: AttachmentAddedOut[];
  attachmentsRemoved: AttachmentRefOut[];
  attachmentsDeletedLocally: AttachmentRefOut[];
};

function hasConflict(row: RowChangeOut): boolean {
  return row.fields.some((field) => field.state === 'conflict');
}

export function groupUpdates(updates: UpdatesOut): UpdateGroups {
  return {
    added: updates.added,
    changed: updates.changed.filter((row) => !hasConflict(row)),
    conflicts: updates.changed.filter(hasConflict),
    removed: updates.removed,
    deletedLocally: updates.deleted_locally,
    attachmentsAdded: updates.attachments_added,
    attachmentsRemoved: updates.attachments_removed,
    attachmentsDeletedLocally: updates.attachments_deleted_locally,
  };
}

export type UpdateCounts = {
  changed: number;
  new: number;
  removed: number;
  conflicts: number;
  parents: number;
};

export function countUpdates(updates: UpdatesOut): UpdateCounts {
  const groups = groupUpdates(updates);

  return {
    changed: groups.changed.length,
    new: groups.added.length,
    removed: groups.removed.length,
    conflicts: groups.conflicts.length,
    parents: groups.attachmentsAdded.length + groups.attachmentsRemoved.length,
  };
}

export function todo(counts: UpdateCounts): number {
  return counts.changed + counts.new + counts.removed + counts.conflicts + counts.parents;
}

// "4 changed, 12 new, 1 removed upstream, 2 conflicts, 3 parents", or that there is nothing.
export function countsSentence(counts: UpdateCounts): string {
  const parts = [
    counts.changed > 0 ? `${counts.changed} changed` : null,
    counts.new > 0 ? `${counts.new} new` : null,
    counts.removed > 0 ? `${counts.removed} removed upstream` : null,
    counts.conflicts > 0
      ? `${counts.conflicts} ${counts.conflicts === 1 ? 'conflict' : 'conflicts'}`
      : null,
    counts.parents > 0
      ? `${counts.parents} ${counts.parents === 1 ? 'parent' : 'parents'} added or removed`
      : null,
  ].filter((part): part is string => part !== null);

  return parts.length === 0 ? 'Up to date' : parts.join(', ');
}

// --- What "apply all clean" takes ----------------------------------------------------------------

export type CleanSelection = {
  actions: UpdateActionIn[];
  changed: number;
  added: number;
  // What it leaves for a decision of its own.
  left: { conflicts: number; collisions: number; removed: number; parents: number };
};

// Every row the library has no edit in, and every new row that clashes with nothing. Never a
// conflict, a name clash, a removal or a parent added: each of those needs its own decision. A row
// the person skipped is not taken either.
export function cleanSelection(
  updates: UpdatesOut,
  skipped: ReadonlySet<string> = new Set(),
): CleanSelection {
  const groups = groupUpdates(updates);
  const actions: UpdateActionIn[] = [];
  let changed = 0;
  let added = 0;

  for (const row of groups.changed) {
    if (skipped.has(rowKey(row))) continue;
    if (!row.fields.some((field) => field.state === 'clean')) continue;

    actions.push({ kind: row.kind, source_id: row.source_id, action: 'apply' });
    changed += 1;
  }

  for (const row of groups.added) {
    if (skipped.has(rowKey(row)) || row.collision !== null) continue;

    actions.push({ kind: row.kind, source_id: row.source_id, action: 'add' });
    added += 1;
  }

  return {
    actions,
    changed,
    added,
    left: {
      conflicts: groups.conflicts.length,
      collisions: groups.added.filter((row) => row.collision !== null).length,
      removed: groups.removed.length,
      parents: groups.attachmentsAdded.length + groups.attachmentsRemoved.length,
    },
  };
}

// The sentence before "apply all clean" is pressed: what it will do and what it leaves.
export function cleanSentence(selection: CleanSelection): string {
  const take = [
    selection.changed > 0
      ? `${selection.changed} ${selection.changed === 1 ? 'change' : 'changes'}`
      : null,
    selection.added > 0 ? `${selection.added} new` : null,
  ].filter((part): part is string => part !== null);

  if (take.length === 0) return 'There is nothing clean to apply.';

  const left = [
    selection.left.conflicts > 0
      ? `${selection.left.conflicts} ${selection.left.conflicts === 1 ? 'conflict' : 'conflicts'}`
      : null,
    selection.left.collisions > 0 ? `${selection.left.collisions} new with a name clash` : null,
    selection.left.removed > 0 ? `${selection.left.removed} removed upstream` : null,
    selection.left.parents > 0
      ? `${selection.left.parents} ${selection.left.parents === 1 ? 'parent' : 'parents'}`
      : null,
  ].filter((part): part is string => part !== null);

  return `Apply ${take.join(' and ')}.${left.length > 0 ? ` Left for you to decide: ${left.join(', ')}.` : ''}`;
}

// --- Actions as the API takes them ---------------------------------------------------------------

export type ConflictChoice = 'keep' | 'take';

// Every conflict named, one way or the other.
export function conflictsSettled(
  row: Pick<RowView, 'conflicts'>,
  choices: ReadonlyMap<string, ConflictChoice>,
): boolean {
  return row.conflicts.every((field) => choices.has(field.field));
}

// Apply a changed row: every clean field is taken, and each conflict as it was chosen.
export function applyAction(
  row: { kind: RowKindName; source_id: string },
  choices: ReadonlyMap<string, ConflictChoice>,
): UpdateActionIn {
  const keep = [...choices].filter(([, choice]) => choice === 'keep').map(([field]) => field);
  const take = [...choices].filter(([, choice]) => choice === 'take').map(([field]) => field);

  return {
    kind: row.kind,
    source_id: row.source_id,
    action: 'apply',
    ...(keep.length > 0 ? { keep_local: keep } : {}),
    ...(take.length > 0 ? { take_upstream: take } : {}),
  };
}

export function detachAction(row: { kind: RowKindName; source_id: string }): UpdateActionIn {
  return { kind: row.kind, source_id: row.source_id, action: 'detach' };
}

export function attachmentAction(
  attachment: Pick<AttachmentRefOut, 'child_source_id' | 'parent_source_id'>,
  action: 'add' | 'detach',
): AttachmentActionIn {
  return {
    child_source_id: attachment.child_source_id,
    parent_source_id: attachment.parent_source_id,
    action,
  };
}

export function attachmentKey(
  attachment: Pick<AttachmentRefOut, 'child_source_id' | 'parent_source_id'>,
): string {
  return `attachment:${attachment.child_source_id}:${attachment.parent_source_id}`;
}

// A parent the repository added, in a sentence, since the interface has no noun for it.
export function attachmentAddedSentence(attachment: AttachmentRefOut): string {
  return `“${attachment.child_name}” would inherit from “${attachment.parent_name}”.`;
}

export function attachmentRemovedSentence(attachment: AttachmentRefOut): string {
  return `“${attachment.child_name}” no longer inherits from “${attachment.parent_name}” in the repository.`;
}

// --- What an apply did ---------------------------------------------------------------------------

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

// The receipt of an apply that was only checked, or of one that was made.
export function appliedSentence(result: ApplyUpdatesOut): string {
  const past = !result.dry_run;
  const parts = [
    result.applied > 0
      ? `${past ? 'applied' : 'apply'} ${plural(result.applied, 'change', 'changes')}`
      : null,
    result.added > 0 ? `${past ? 'added' : 'add'} ${result.added} new` : null,
    result.detached > 0 ? `${past ? 'detached' : 'detach'} ${result.detached}` : null,
    result.attachments_added > 0
      ? `${past ? 'added' : 'add'} ${plural(result.attachments_added, 'parent', 'parents')}`
      : null,
    result.attachments_detached > 0
      ? `${past ? 'detached' : 'detach'} ${plural(result.attachments_detached, 'parent', 'parents')}`
      : null,
  ].filter((part): part is string => part !== null);

  if (parts.length === 0) {
    return past ? 'Nothing was applied.' : 'Nothing would be applied. Nothing has changed.';
  }

  const text = parts.join(', ');
  const sentence = past ? `${text.charAt(0).toUpperCase()}${text.slice(1)}.` : `Would ${text}.`;

  return past ? sentence : `${sentence} Nothing has changed yet.`;
}

// A field the API could not apply, and why: it keeps being offered.
export function notAppliedSentence(entry: NotAppliedOut): string {
  const subject = entry.name ?? 'A row';
  const what =
    entry.kind === 'attachment'
      ? `the parent ${entry.label ?? ''}`.trim()
      : entry.field.startsWith('stats:')
        ? `the value of ${entry.label ?? 'a stat'}`
        : entry.field.startsWith('formulas:')
          ? `the formula of ${entry.label ?? 'a stat'}`
          : (WORDS[entry.field]?.label.toLowerCase() ?? entry.field.replace(/_/g, ' '));

  return `${subject}: ${what} was left as it is. ${entry.reason.replace(/\.$/, '')}. It is offered again next time.`;
}

// --- The library's inbox -------------------------------------------------------------------------

// Repositories with the most to do first, then by name.
export function inboxOrder<T extends { name: string; counts: UpdateCounts | null }>(
  rows: T[],
): T[] {
  const weight = (row: T) => (row.counts ? todo(row.counts) : -1);

  return [...rows].sort(
    (a, b) => weight(b) - weight(a) || a.name.localeCompare(b.name, 'en', { sensitivity: 'base' }),
  );
}
