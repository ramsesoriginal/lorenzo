// "Why is my armour 15?" (RFC 0043): a calculated stat's explanation, in words and parts. The shape is
// the API's (ADR 0276); this only says it.

import type { components } from './api';
import { statLabel } from './statLabel';

export type Explanation = components['schemas']['StatExplanationOut'];

export type Explained = {
  /** The formula, as a sentence. */
  text: string;
  /** What it read: a label and the value. */
  parts: { label: string; value: string }[];
};

const ROUNDING: Record<string, string> = {
  none: '',
  floor: ', rounded down',
  ceil: ', rounded up',
  round: ', rounded',
};

const COMPARATORS: Record<string, string> = {
  gt: 'is more than',
  gte: 'is at least',
  lt: 'is less than',
  lte: 'is at most',
  eq: 'equals',
  ne: 'is not',
};

const shown = (value: number | string | boolean | null): string =>
  value === null ? '—' : typeof value === 'boolean' ? (value ? 'On' : 'Off') : String(value);

/** The explanation in words. `names` gives a definition's name by its id, for the formula's parts. */
export function explain(explanation: Explanation, names: ReadonlyMap<string, string>): Explained {
  const formula = explanation.formula;
  const label = (id: string | null | undefined): string =>
    statLabel(names.get(id ?? '') ?? 'a stat');
  const parts = explanation.inputs.map((input) => ({
    label: statLabel(input.name),
    value: shown(input.value),
  }));

  if (!formula) {
    return { text: 'A value set on this being.', parts: [] };
  }

  switch (formula.kind) {
    case 'linear': {
      const offset = Number(formula.offset);
      const added = offset === 0 ? '' : offset > 0 ? ` + ${offset}` : ` − ${Math.abs(offset)}`;
      const rounding = ROUNDING[formula.round_mode] ?? '';

      return {
        text: `${label(formula.source_stat_definition_id)} × ${formula.multiplier}${added}${rounding}`,
        parts,
      };
    }
    case 'sum': {
      const terms = formula.terms
        .map((term) =>
          Number(term.coefficient) === 1
            ? label(term.stat_definition_id)
            : `${term.coefficient} × ${label(term.stat_definition_id)}`,
        )
        .join(' + ');
      const offset = Number(formula.offset);
      const added = offset === 0 ? '' : offset > 0 ? ` + ${offset}` : ` − ${Math.abs(offset)}`;
      const rounding = ROUNDING[formula.round_mode] ?? '';

      return { text: `${terms}${added}${rounding}`, parts };
    }
    case 'comparison': {
      const right = formula.right_stat_definition_id
        ? label(formula.right_stat_definition_id)
        : (formula.right_constant ?? '');

      return {
        text:
          `${label(formula.left_stat_definition_id)} ${COMPARATORS[formula.comparator] ?? formula.comparator} ${right}` +
          (formula.true_value !== undefined && formula.true_value !== null
            ? `: ${formula.true_value}, otherwise ${formula.false_value ?? '—'}`
            : ''),
        parts,
      };
    }
    case 'contents': {
      const counted = explanation.contents;

      return {
        text: `${label(formula.source_stat_definition_id)} of what is inside, each times how many`,
        parts: counted ? [{ label: 'Things inside', value: String(counted.things) }] : parts,
      };
    }
  }
}
