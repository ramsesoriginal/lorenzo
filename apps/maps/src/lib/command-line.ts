// The command line under the Map (MP6): a line of text for what a pointer does, so every command has a
// keyboard twin. This is only the reading of a line, pure and tested without a browser; the editor does
// what it says. A tool is named by its name, and a planned tool says why it does nothing.

import { SEED_MOST, seedOf } from './generator';
import { unitOf } from './height';
import {
  numberFor,
  type OptionValue,
  optionsOf,
  type ToolDecl,
  type ToolOption,
  usable,
} from './tools';

export type Command =
  | { kind: 'tool'; tool: ToolDecl }
  | { kind: 'planned'; tool: ToolDecl }
  | { kind: 'unavailable'; tool: ToolDecl }
  | { kind: 'undo' }
  | { kind: 'redo' }
  | { kind: 'fit' }
  | { kind: 'help' }
  | { kind: 'point'; at: [number, number] }
  | { kind: 'done' }
  | { kind: 'select'; name: string }
  | { kind: 'place'; name: string; at: [number, number] }
  | { kind: 'option'; option: ToolOption; value: OptionValue }
  /** A generator's own commands (ADR 0475). */
  | { kind: 'roll' }
  | { kind: 'apply' }
  | { kind: 'discard' }
  | { kind: 'compare'; on: boolean }
  /** A stroke of the Height brush at one point (ADR 0480). */
  | { kind: 'brush'; lower: boolean; at: [number, number] }
  | { kind: 'error'; message: string };

export const HELP = [
  'Tool name (for example Line): choose that tool.',
  'PLACE name x,y: put a place of the library on the Map at that point.',
  'SELECT name: select a place on the Map.',
  'x,y: the next point of what is being drawn; DONE finishes a line, an area or cells.',
  'An option of the tool by its name, for example SNAP OFF, TENSION 0.4 or UNIT m.',
  'For a generator: SEED n, ROLL, COMPARE ON or OFF, APPLY, DISCARD.',
  'For the Height brush: RAISE x,y or LOWER x,y, then APPLY or DISCARD.',
  'UNDO, REDO, FIT (frame the whole sheet), HELP.',
].join(' ');

const POINT = /^(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)$/;

export function parsePoint(text: string): [number, number] | null {
  const m = POINT.exec(text.trim());
  return m ? [Number(m[1]), Number(m[2])] : null;
}

export function parseCommand(
  line: string,
  tools: ToolDecl[],
  context: { grid: boolean; sphere: boolean; tool?: ToolDecl },
): Command | null {
  const text = line.trim();
  if (!text) return null;
  const typed = parsePoint(text);
  if (typed) return { kind: 'point', at: typed };
  const word = (text.split(/\s+/, 1)[0] ?? '').toLowerCase();
  const rest = text.slice(word.length).trim();
  switch (word) {
    case 'undo':
      return { kind: 'undo' };
    case 'redo':
      return { kind: 'redo' };
    case 'fit':
      return { kind: 'fit' };
    case 'done':
    case 'finish':
      return { kind: 'done' };
    case 'help':
    case '?':
      return { kind: 'help' };
    case 'roll':
      return { kind: 'roll' };
    case 'raise':
    case 'lower': {
      const at = parsePoint(rest);
      return at
        ? { kind: 'brush', lower: word === 'lower', at }
        : {
            kind: 'error',
            message: `${word.toUpperCase()} takes a point, for example ${word.toUpperCase()} 500,400.`,
          };
    }
    case 'apply':
      return { kind: 'apply' };
    case 'discard':
      return { kind: 'discard' };
    case 'compare': {
      const value = rest.toLowerCase();
      return value === 'on' || value === 'off'
        ? { kind: 'compare', on: value === 'on' }
        : { kind: 'error', message: 'COMPARE takes ON or OFF.' };
    }
    case 'select':
      return rest
        ? { kind: 'select', name: rest }
        : { kind: 'error', message: 'SELECT needs a name.' };
    case 'place': {
      const at = rest.lastIndexOf(' ');
      const point = at < 0 ? null : parsePoint(rest.slice(at + 1));
      const name = at < 0 ? '' : rest.slice(0, at).trim();
      return point && name
        ? { kind: 'place', name, at: point }
        : {
            kind: 'error',
            message: 'PLACE needs a name and a point, for example PLACE Harbour 120,80.',
          };
    }
  }
  // A tool's whole name comes before an option's word: "Height line" is a tool, "HEIGHT 250" is not.
  const tool = tools.find((t) => t.name.toLowerCase() === text.toLowerCase());
  if (tool) {
    if (tool.state === 'planned') return { kind: 'planned', tool };
    return usable(tool, context) ? { kind: 'tool', tool } : { kind: 'unavailable', tool };
  }
  if (tools.some((t) => (t.options ?? []).some((option) => option.word === word))) {
    return parseOption(word, rest, context);
  }
  return { kind: 'error', message: `“${text}” is not a command. Type HELP for the list.` };
}

/** An option's word and its value, for the tool that is on (ADR 0470). */
function parseOption(
  word: string,
  rest: string,
  context: { grid: boolean; tool?: ToolDecl },
): Command {
  const name = word.toUpperCase();
  const tool = context.tool;
  if (!tool)
    return { kind: 'error', message: `Choose a tool first: ${name} is an option of a tool.` };
  const offered = optionsOf(tool, context);
  const option = offered.find((o) => o.word === word);
  if (!option) {
    const has = offered.map((o) => o.word.toUpperCase()).join(', ');
    return {
      kind: 'error',
      message: has
        ? `${tool.name} has no option ${name} on this Map. It has ${has}.`
        : `${tool.name} has no options on this Map.`,
    };
  }
  if (option.type === 'number') {
    const typed = /^-?\d+(?:\.\d+)?$/.test(rest) ? numberFor(option, Number(rest)) : null;
    // A range as wide as the format's own is not worth saying.
    const range = option.most - option.least > 1e9 ? '' : ` from ${option.least} to ${option.most}`;
    return typed === null
      ? { kind: 'error', message: `${name} takes a number${range}.` }
      : { kind: 'option', option, value: typed };
  }
  if (option.type === 'choice') {
    const typed = rest.toLowerCase();
    const found = option.choices.find(
      ([value, title]) => (value !== '' && value === typed) || title.toLowerCase() === typed,
    );
    return found
      ? { kind: 'option', option, value: found[0] }
      : {
          kind: 'error',
          message: `${name} takes one of: ${option.choices.map(([, title]) => title.toLowerCase()).join(', ')}.`,
        };
  }
  if (option.type === 'map') {
    // The name is matched against the Maps offered by the editor, which reads them.
    return rest
      ? { kind: 'option', option, value: rest }
      : { kind: 'error', message: `${name} takes the name of a Map, or THIS for this Map.` };
  }
  if (option.type === 'seed') {
    const typed = seedOf(rest);
    return typed === null
      ? { kind: 'error', message: `${name} takes a whole number from 0 to ${SEED_MOST}.` }
      : { kind: 'option', option, value: typed };
  }
  if (option.type === 'text') {
    const typed = unitOf(rest);
    return typed === null || [...typed].length > option.longest
      ? { kind: 'error', message: `${name} takes 1 to ${option.longest} characters.` }
      : { kind: 'option', option, value: typed };
  }
  const value = rest.toLowerCase();
  if (value === 'on') return { kind: 'option', option, value: true };
  if (value === 'off') return { kind: 'option', option, value: false };
  return { kind: 'error', message: `${name} takes ON or OFF.` };
}
