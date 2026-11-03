// What the review element takes (ADR 0389). It is plain data: the host has already turned whatever
// it holds (an API's update rows, a device's queued commands) into text, so the element never sees
// an API type, an id or a model.

/** Whose value to keep: the host's own change (`mine`), or what the other side has (`theirs`). */
export type ReviewSide = 'mine' | 'theirs';

/**
 * One value, already in a person's words. A string is shown as it is, as text and never as markup.
 * `empty` is a field with no value at all; `deleted` is a thing the other side removed.
 */
export type ReviewValue = string | { readonly kind: 'empty' } | { readonly kind: 'deleted' };

export const EMPTY: ReviewValue = { kind: 'empty' };
export const DELETED: ReviewValue = { kind: 'deleted' };

/**
 * What changed in one field.
 *
 * - `value`: what it was (`was`), what the other side has now (`theirs`) and, when the host changed
 *   it too, what the host has (`mine`). Without `mine` the host has no change of its own to weigh.
 * - `set`: for something made of parts (what an entry inherits from), what was added and what was
 *   taken away, as names.
 */
export type ReviewChange =
  | {
      readonly kind: 'value';
      readonly was: ReviewValue;
      readonly theirs: ReviewValue;
      readonly mine?: ReviewValue;
    }
  | {
      readonly kind: 'set';
      readonly added: readonly string[];
      readonly removed: readonly string[];
    };

export type ReviewItem = {
  /** Unique within one review; it comes back in the callback. */
  readonly id: string;
  /** The field in the product's words: "Name", "Stat: Weight". */
  readonly label: string;
  readonly change: ReviewChange;
  /** Why the change cannot be taken, or anything else worth one sentence under the values. */
  readonly note?: string;
  /**
   * Present when the person has to choose between `mine` and `theirs`. `chosen` is what is chosen
   * now, or `null` while nothing is. Absent: the field is shown and nothing is asked.
   */
  readonly choice?: { readonly chosen: ReviewSide | null };
};

/**
 * `choose`: the choice is a pair of radio buttons that the host reads later, when it applies
 * everything at once; `onChoose` hears each change. `act`: the choice is two buttons, and pressing
 * one is the choice; the host acts in `onChoose` and draws again.
 */
export type ReviewMode = 'choose' | 'act';

export type ReviewOptions = {
  /** Default `choose`. */
  readonly mode?: ReviewMode;
  /** Told when a side is chosen (`choose`) or pressed (`act`). */
  readonly onChoose?: (id: string, side: ReviewSide) => void;
  /** The host's own words where they differ from the defaults. */
  readonly words?: Partial<ReviewWords>;
};

/** Every word the element says, so that a host can change one without touching the rest. */
export type ReviewWords = {
  /** The value before either side changed it. */
  was: string;
  /** What the other side has now. */
  theirs: string;
  /** What the host has. */
  mine: string;
  added: string;
  removed: string;
  noValue: string;
  deleted: string;
  keepMine: string;
  takeTheirs: string;
  /** The question over the radio buttons of `choose`. */
  choiceLegend: string;
  /** The name of the pair of buttons of `act`, for a field. */
  chooseFor: (label: string) => string;
  /** Said politely, for a screen reader, when a side is chosen. */
  keptMine: (label: string) => string;
  tookTheirs: (label: string) => string;
};
