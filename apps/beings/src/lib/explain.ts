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

      // What is counted, as the options say (ADR 0447): all of it, or what is switched on.
      const aggregate = formula.aggregate ?? 'sum';
      const stat = formula.source_stat_definition_id
        ? label(formula.source_stat_definition_id)
        : '';
      const which = formula.only_active ? ' that is switched on' : '';
      const text =
        aggregate === 'count'
          ? `How many things inside${which}`
          : aggregate === 'sum'
            ? `${stat} of what is inside${which}, each times how many`
            : `The ${aggregate === 'min' ? 'smallest' : 'largest'} ${stat} of what is inside${which}`;

      return {
        text,
        parts: counted ? [{ label: 'Things inside', value: String(counted.things) }] : parts,
      };
    }
    case 'min':
    case 'max': {
      // A cap or a floor (ADR 0444): what it compares, the way it is said.
      const operands = formula.inputs
        .map((input) =>
          input.stat_definition_id ? label(input.stat_definition_id) : String(input.constant ?? ''),
        )
        .join(', ');
      const rounding = ROUNDING[formula.round_mode] ?? '';

      return {
        text: `The ${formula.kind === 'min' ? 'smaller' : 'larger'} of ${operands}${rounding}`,
        parts,
      };
    }
    case 'product': {
      // ADR 0445: the factors, times a constant, plus an offset.
      const factors = formula.factors.map((id) => label(id)).join(' × ');
      const multiplier = Number(formula.multiplier);
      const times = multiplier === 1 ? '' : ` × ${multiplier}`;
      const offset = Number(formula.offset);
      const added = offset === 0 ? '' : offset > 0 ? ` + ${offset}` : ` − ${Math.abs(offset)}`;
      const rounding = ROUNDING[formula.round_mode] ?? '';

      return { text: `${factors}${times}${added}${rounding}`, parts };
    }
    case 'ratio': {
      const by = formula.denominator_stat_definition_id
        ? label(formula.denominator_stat_definition_id)
        : String(formula.denominator_constant ?? '');
      const multiplier = Number(formula.multiplier);
      const times = multiplier === 1 ? '' : ` × ${multiplier}`;
      const offset = Number(formula.offset);
      const added = offset === 0 ? '' : offset > 0 ? ` + ${offset}` : ` − ${Math.abs(offset)}`;
      const rounding = ROUNDING[formula.round_mode] ?? '';
      const lost = explanation.division_rounded ? ', the division rounded to 28 digits' : '';

      return {
        text: `${label(formula.numerator_stat_definition_id)} ÷ ${by}${times}${added}${rounding}${lost}`,
        parts,
      };
    }
    case 'dice_value': {
      // ADR 0463: what is read of a dice stat, the way it is said.
      const read = { min: 'smallest', max: 'largest', average: 'average' }[formula.as];
      const rounding = ROUNDING[formula.round_mode] ?? '';

      return {
        text: `The ${read} roll of ${label(formula.source_stat_definition_id)}${rounding}`,
        parts,
      };
    }
    case 'dice': {
      // ADR 0464: the dice a count and a number of sides make, each a stat or a constant.
      const count = formula.count_stat_definition_id
        ? label(formula.count_stat_definition_id)
        : String(formula.count_constant ?? '');
      const sides = formula.sides_stat_definition_id
        ? label(formula.sides_stat_definition_id)
        : String(formula.sides_constant ?? '');

      return { text: `${count} dice of ${sides} sides`, parts };
    }
    case 'select': {
      // A value from a table (ADR 0446): which step the source reached.
      const chosen = explanation.chosen;
      const step =
        chosen === null || chosen === undefined
          ? null
          : chosen.position === null
            ? 'none matched, so the default'
            : `step ${chosen.position + 1} (${chosen.key})`;

      return {
        text: `${label(formula.source_stat_definition_id)} looked up in a table of ${formula.steps.length} steps`,
        parts: step === null ? parts : [...parts, { label: 'Step taken', value: step }],
      };
    }
  }
}
