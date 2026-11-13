// The keys of the tools, remappable (MP6): each tool starts with the key its declaration gives it, and a
// person may choose another letter for it. The choice is theirs alone, kept in this browser. Pure over a
// storage, so it is tested without a browser.

import { TOOLS, type ToolDecl } from './tools';

export const KEYMAP_STORAGE = 'lorenzo:maps:keys';

/** Keys the page keeps for itself: the command line's. */
export const RESERVED = ['/'];

type Store = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

export type KeyMap = {
  keyOf(tool: ToolDecl): string;
  toolFor(key: string): ToolDecl | undefined;
  /** Gives a tool a key; says why not when it cannot be that key. */
  set(tool: ToolDecl, key: string): string | null;
  reset(): void;
  isChanged(tool: ToolDecl): boolean;
};

export function createKeyMap(store: Store | null, tools: ToolDecl[] = TOOLS): KeyMap {
  let mine: Record<string, string> = {};
  try {
    const raw = store?.getItem(KEYMAP_STORAGE);
    const parsed = raw ? (JSON.parse(raw) as unknown) : null;
    if (parsed && typeof parsed === 'object') {
      for (const [id, key] of Object.entries(parsed)) {
        if (typeof key === 'string' && key.length === 1 && tools.some((t) => t.id === id))
          mine[id] = key.toLowerCase();
      }
    }
  } catch {
    mine = {};
  }
  const keyOf = (tool: ToolDecl) => mine[tool.id] ?? tool.key;
  const save = () => {
    try {
      if (Object.keys(mine).length) store?.setItem(KEYMAP_STORAGE, JSON.stringify(mine));
      else store?.removeItem(KEYMAP_STORAGE);
    } catch {
      // A browser that keeps nothing keeps the keys for this page only.
    }
  };
  return {
    keyOf,
    toolFor: (key) => tools.find((tool) => keyOf(tool) === key.toLowerCase()),
    set(tool, key) {
      const k = key.toLowerCase();
      if (RESERVED.includes(k)) return `${k} is kept for the command line.`;
      if (k.length !== 1 || !/^[a-z0-9]$/.test(k)) return 'Use one letter or digit.';
      const other = tools.find((t) => t.id !== tool.id && keyOf(t) === k);
      if (other) return `${k.toUpperCase()} is ${other.name}'s key.`;
      if (k === tool.key) delete mine[tool.id];
      else mine[tool.id] = k;
      save();
      return null;
    },
    reset() {
      mine = {};
      save();
    },
    isChanged: (tool) => keyOf(tool) !== tool.key,
  };
}
