// The command line under the Map (MP6): a line of text for what a pointer does, so every command has a
// keyboard twin. This is only the reading of a line, pure and tested without a browser; the editor does
// what it says. A tool is named by its name, and a planned tool says why it does nothing.

import { type ToolDecl, usable } from './tools';

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
  | { kind: 'error'; message: string };

export const HELP = [
  'Tool name (for example Line): choose that tool.',
  'PLACE name x,y: put a place of the library on the Map at that point.',
  'SELECT name: select a place on the Map.',
  'x,y: the next point of what is being drawn; DONE finishes a line, an area or cells.',
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
  context: { grid: boolean; sphere: boolean },
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
  const tool = tools.find((t) => t.name.toLowerCase() === text.toLowerCase());
  if (tool) {
    if (tool.state === 'planned') return { kind: 'planned', tool };
    return usable(tool, context) ? { kind: 'tool', tool } : { kind: 'unavailable', tool };
  }
  return { kind: 'error', message: `“${text}” is not a command. Type HELP for the list.` };
}
