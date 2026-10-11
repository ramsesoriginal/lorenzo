// Formulas that work out a stat (ADR 0253): what they are, how they read and are written for the
// API, and whether a draft can be saved. Plain data and pure functions, so they are tested alone.

import type { StatDef } from './transport';

export type Round = 'none' | 'floor' | 'ceil' | 'round' | 'truncate';
export const ROUNDS: readonly Round[] = ['none', 'floor', 'ceil', 'round', 'truncate'];
export type Comparator = 'lt' | 'le' | 'eq' | 'ne' | 'ge' | 'gt';
export const COMPARATORS: readonly [Comparator, string][] = [
  ['lt', 'is less than'],
  ['le', 'is at most'],
  ['eq', 'equals'],
  ['ne', 'is not'],
  ['ge', 'is at least'],
  ['gt', 'is more than'],
];

/** Numbers are kept as the text a person typed, so a decimal reaches the API exactly. */
export type Formula =
  | { kind: 'linear'; source: string; multiplier: string; offset: string; round: Round }
  | { kind: 'sum'; terms: { stat: string; coefficient: string }[]; offset: string; round: Round }
  | { kind: 'contents'; source: string }
  | {
      kind: 'comparison';
      left: string;
      comparator: Comparator;
      right: { stat: string } | { constant: string };
      trueValue: string;
      falseValue: string;
    };
export type Kind = Formula['kind'];

/** What a person calls each kind. */
export const KIND_LABEL: Record<Kind, string> = {
  linear: 'Scale',
  sum: 'Add up',
  contents: 'Contents',
  comparison: 'Compare',
};
export const KINDS: readonly Kind[] = ['sum', 'linear', 'contents', 'comparison'];

const NUMBER = /^-?\d+(\.\d+)?$/;
const clean = (text: string): string => text.trim().replace(',', '.');
/** A decimal as typed (a comma is read as a point). */
export const isDecimal = (text: string): boolean => NUMBER.test(clean(text));

const isNumeric = (d: StatDef | undefined): boolean => d?.type === 'int' || d?.type === 'float';

/** A starting formula of this kind, reading the first stats that fit it. */
export function starting(kind: Kind, defs: readonly StatDef[], target?: string): Formula {
  const numbers = defs.filter((d) => isNumeric(d) && d.id !== target);
  const first = numbers[0]?.id ?? '';
  const second = numbers[1]?.id ?? first;
  if (kind === 'sum')
    return { kind, terms: [{ stat: first, coefficient: '1' }], offset: '0', round: 'none' };
  if (kind === 'linear')
    return { kind, source: first, multiplier: '1', offset: '0', round: 'none' };
  if (kind === 'contents') return { kind, source: first };
  return {
    kind,
    left: first,
    comparator: 'ge',
    right: { stat: second },
    trueValue: '',
    falseValue: '',
  };
}

/** The same formula as a sentence: "2 × Weight + 1 × Contents weight". */
export function describe(f: Formula, nameOf: (id: string) => string): string {
  const tail = (offset: string, round: Round) => {
    const n = clean(offset);
    const added =
      n !== '0' && n !== '' ? ` ${n.startsWith('-') ? '−' : '+'} ${n.replace('-', '')}` : '';
    return `${added}${round !== 'none' ? `, rounded (${round})` : ''}`;
  };
  if (f.kind === 'sum')
    return `${f.terms.map((t) => `${clean(t.coefficient)} × ${nameOf(t.stat)}`).join(' + ')}${tail(f.offset, f.round)}`;
  if (f.kind === 'linear')
    return `${nameOf(f.source)} × ${clean(f.multiplier)}${tail(f.offset, f.round)}`;
  if (f.kind === 'contents') return `${nameOf(f.source)} of everything inside, by how many`;
  const right = 'stat' in f.right ? nameOf(f.right.stat) : clean(f.right.constant);
  const word = COMPARATORS.find(([c]) => c === f.comparator)?.[1] ?? f.comparator;
  return `${nameOf(f.left)} ${word} ${right}`;
}

/** Why a draft cannot be saved, one message each; empty when it can. */
export function problems(f: Formula, defs: readonly StatDef[], target: string): string[] {
  const byId = new Map(defs.map((d) => [d.id, d]));
  const out: string[] = [];
  const reads = (id: string, what: string) => {
    if (!id || !byId.has(id)) out.push(`Choose the stat ${what}.`);
    else if (id === target) out.push('A stat cannot be worked out from itself.');
  };
  const number = (text: string, what: string) => {
    if (!isDecimal(text)) out.push(`${what} must be a number.`);
  };
  if (f.kind === 'sum') {
    if (!f.terms.length) out.push('Add at least one stat.');
    if (f.terms.length > 20) out.push('A sum reads at most 20 stats.');
    f.terms.forEach((t, i) => {
      reads(t.stat, `in row ${i + 1}`);
      number(t.coefficient, `The number in row ${i + 1}`);
    });
    const ids = f.terms.map((t) => t.stat);
    if (new Set(ids).size !== ids.length) out.push('Each stat can be added once.');
    number(f.offset, 'The number added');
  } else if (f.kind === 'linear') {
    reads(f.source, 'to scale');
    number(f.multiplier, 'The multiplier');
    number(f.offset, 'The number added');
  } else if (f.kind === 'contents') reads(f.source, 'to count inside');
  else {
    reads(f.left, 'to compare');
    if ('stat' in f.right) reads(f.right.stat, 'to compare with');
    else number(f.right.constant, 'The number to compare with');
    const t = byId.get(target);
    if (t && t.type !== 'bool' && (!f.trueValue.trim() || !f.falseValue.trim()))
      out.push('Say what it is when the comparison holds, and when it does not.');
  }
  return out;
}

const normal = (f: Formula): unknown => {
  if (f.kind === 'sum')
    return {
      ...f,
      terms: f.terms.map((t) => ({ ...t, coefficient: Number(clean(t.coefficient)) })),
      offset: Number(clean(f.offset)),
    };
  if (f.kind === 'linear')
    return { ...f, multiplier: Number(clean(f.multiplier)), offset: Number(clean(f.offset)) };
  if (f.kind === 'comparison' && 'constant' in f.right)
    return { ...f, right: { constant: Number(clean(f.right.constant)) } };
  return f;
};

/** Whether two formulas are the same, whatever the spelling of a number. */
export function same(a: Formula, b: Formula): boolean {
  return JSON.stringify(normal(a)) === JSON.stringify(normal(b));
}

/** What the API takes (`FormulaBody`). */
export type Body =
  | {
      kind: 'linear';
      source_stat_definition_id: string;
      multiplier: string;
      offset: string;
      round_mode: Round;
    }
  | {
      kind: 'sum';
      terms: { stat_definition_id: string; coefficient: string }[];
      offset: string;
      round_mode: Round;
    }
  | { kind: 'contents'; source_stat_definition_id: string }
  | {
      kind: 'comparison';
      left_stat_definition_id: string;
      comparator: Comparator;
      right_stat_definition_id?: string | null;
      right_constant?: string | null;
      true_value?: string | null;
      false_value?: string | null;
    };

export function toBody(f: Formula): Body {
  if (f.kind === 'sum')
    return {
      kind: 'sum',
      terms: f.terms.map((t) => ({
        stat_definition_id: t.stat,
        coefficient: clean(t.coefficient),
      })),
      offset: clean(f.offset),
      round_mode: f.round,
    };
  if (f.kind === 'linear')
    return {
      kind: 'linear',
      source_stat_definition_id: f.source,
      multiplier: clean(f.multiplier),
      offset: clean(f.offset),
      round_mode: f.round,
    };
  if (f.kind === 'contents') return { kind: 'contents', source_stat_definition_id: f.source };
  return {
    kind: 'comparison',
    left_stat_definition_id: f.left,
    comparator: f.comparator,
    right_stat_definition_id: 'stat' in f.right ? f.right.stat : null,
    right_constant: 'constant' in f.right ? clean(f.right.constant) : null,
    true_value: f.trueValue.trim() || null,
    false_value: f.falseValue.trim() || null,
  };
}

/** What the API answers (`FormulaBody` as read), as a formula. Numbers come back as numbers or text. */
export function fromBody(b: Body | Record<string, unknown>): Formula {
  const body = b as Record<string, unknown>;
  const text = (v: unknown) => (v === null || v === undefined ? '' : String(v));
  const round = (v: unknown): Round => (ROUNDS.includes(v as Round) ? (v as Round) : 'none');
  if (body.kind === 'sum')
    return {
      kind: 'sum',
      terms: (body.terms as { stat_definition_id: string; coefficient: unknown }[]).map((t) => ({
        stat: t.stat_definition_id,
        coefficient: text(t.coefficient),
      })),
      offset: text(body.offset),
      round: round(body.round_mode),
    };
  if (body.kind === 'linear')
    return {
      kind: 'linear',
      source: text(body.source_stat_definition_id),
      multiplier: text(body.multiplier),
      offset: text(body.offset),
      round: round(body.round_mode),
    };
  if (body.kind === 'contents')
    return { kind: 'contents', source: text(body.source_stat_definition_id) };
  return {
    kind: 'comparison',
    left: text(body.left_stat_definition_id),
    comparator: body.comparator as Comparator,
    right: body.right_stat_definition_id
      ? { stat: text(body.right_stat_definition_id) }
      : { constant: text(body.right_constant) },
    trueValue: text(body.true_value),
    falseValue: text(body.false_value),
  };
}
