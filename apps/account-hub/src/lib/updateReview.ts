// A changed field of the update inbox, as the shared review element takes it (ADR 0389,
// packages/repo-ui): the words of `describeField` handed over as plain data, so the element draws
// Was / Now / Yours and the choice and the inbox keeps what the choices mean. No DOM; unit-tested.

import { EMPTY, type ReviewItem, type ReviewSide, type ReviewValue } from '@lorenzo/repo-ui';
import { type ConflictChoice, type FieldView, NONE } from './updates';

// The page's choice for a conflict ("keep yours", "take the update") as a side of the review.
export function sideOf(choice: ConflictChoice | undefined): ReviewSide | null {
  if (choice === undefined) return null;

  return choice === 'keep' ? 'mine' : 'theirs';
}

// ...and back: the side the element reports, as the choice the apply action is built from.
export function choiceOf(side: ReviewSide): ConflictChoice {
  return side === 'mine' ? 'keep' : 'take';
}

// A value the inbox could not name is "(none)": the element says it as the lack of a value.
function valueFor(text: string | null): ReviewValue {
  return text === null || text === NONE ? EMPTY : text;
}

// One field of a row. A conflict asks for a choice, and `chosen` is what the page remembers of it.
export function reviewItem(field: FieldView, chosen?: ConflictChoice): ReviewItem {
  const asked = field.state === 'conflict';
  const isSet = field.added !== null || field.removed !== null;

  return {
    id: field.field,
    label: field.label,
    change: isSet
      ? { kind: 'set', added: field.added ?? [], removed: field.removed ?? [] }
      : {
          kind: 'value',
          was: valueFor(field.was),
          theirs: valueFor(field.now),
          ...(field.yours === null ? {} : { mine: valueFor(field.yours) }),
        },
    ...(field.note === null ? {} : { note: field.note }),
    ...(asked ? { choice: { chosen: sideOf(chosen) } } : {}),
  };
}
