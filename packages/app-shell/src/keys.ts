// The keyboard model (ADR 0414): Ctrl or Cmd K opens the palette, `?` lists the shortcuts, and G then a
// letter goes somewhere. Single-key shortcuts can be switched off (WCAG 2.1.4); the ones with Ctrl or
// Cmd always work. A key typed into a field is the field's. Pure, so it is tested without a browser.

/** What a "G then letter" goes to: an app by its registry name, or one of the shell's own places. */
export const GO_KEYS: Record<string, string> = {
  h: 'home',
  s: 'sessions',
  b: 'beings',
  i: 'inventory_web',
  c: 'calendars',
  m: 'maps',
  w: 'writing',
  o: 'social',
  r: 'bench',
  a: 'account_hub',
  l: 'library',
  t: 'theme',
};

/** The key a place has, for the palette's hints ("G S"). */
export function goChord(target: string): string | undefined {
  const entry = Object.entries(GO_KEYS).find(([, value]) => value === target);

  return entry ? `G ${entry[0].toUpperCase()}` : undefined;
}

export type KeyInput = {
  key: string;
  ctrlKey: boolean;
  metaKey: boolean;
  altKey: boolean;
  shiftKey: boolean;
  /** Whether the key was typed into a field, a select or an editor. */
  typing: boolean;
};

export type KeymapOptions = {
  /** Read at each key, so the switch takes effect at once. */
  singleKeys(): boolean;
  onGo(target: string): void;
  onHelp(): void;
  onPalette(): void;
  now?(): number;
  /** How long after G a letter still counts. */
  chordMs?: number;
};

/**
 * A key handler. `handle` returns true when the key was used, and the caller then stops the browser's
 * own action for it.
 */
export function createKeymap(options: KeymapOptions): { handle(input: KeyInput): boolean } {
  const now = options.now ?? (() => Date.now());
  const chordMs = options.chordMs ?? 1500;
  let chordAt: number | null = null;

  return {
    handle(input) {
      const key = input.key.toLowerCase();

      // With Ctrl or Cmd: always on, and in a field too.
      if ((input.ctrlKey || input.metaKey) && !input.altKey && key === 'k' && !input.shiftKey) {
        chordAt = null;
        options.onPalette();

        return true;
      }

      if (input.ctrlKey || input.metaKey || input.altKey || input.typing) {
        chordAt = null;

        return false;
      }

      if (!options.singleKeys()) {
        chordAt = null;

        return false;
      }

      if (chordAt !== null) {
        const fresh = now() - chordAt <= chordMs;

        chordAt = null;

        if (fresh) {
          const target = GO_KEYS[key];

          if (target) {
            options.onGo(target);

            return true;
          }
        }
      }

      if (key === 'g' && !input.shiftKey) {
        chordAt = now();

        return true;
      }

      if (input.key === '?') {
        options.onHelp();

        return true;
      }

      return false;
    },
  };
}
