// The editor's keyboard rules as a pure function (ADR 0510), so that another editor over the same
// text, such as the semilive one, behaves the same without copying them.
import { ACTIONS, type ActionName, indent, newline, type State } from './actions';

export type KeyInput = {
  key: string;
  ctrlKey: boolean;
  metaKey: boolean;
  altKey: boolean;
  shiftKey: boolean;
  isComposing?: boolean;
};

export type KeyResult = { handled: true; state: State } | { handled: false };

export const SHORTCUTS = new Map(
  Object.entries(ACTIONS).flatMap(([name, a]) => ('key' in a ? [[a.key, name as ActionName]] : [])),
);

/**
 * What a key does to the text. `afterEscape` is whether the key before was Escape: Escape, then
 * Tab, leaves the editor, so taking Tab over never traps a keyboard user.
 */
export function keyAction(e: KeyInput, state: State, afterEscape = false): KeyResult {
  const modified = e.ctrlKey || e.metaKey || e.altKey;
  if (e.key === 'Tab' && !modified) {
    if (afterEscape) return { handled: false };
    return { handled: true, state: indent(e.shiftKey)(state) };
  }
  if (e.key === 'Enter' && !modified && !e.shiftKey && !e.isComposing) {
    const next = newline(state);
    return next ? { handled: true, state: next } : { handled: false };
  }
  if ((e.ctrlKey || e.metaKey) && !e.altKey) {
    const name = SHORTCUTS.get(e.key.toLowerCase());
    if (name) return { handled: true, state: ACTIONS[name].run(state) };
  }
  return { handled: false };
}
