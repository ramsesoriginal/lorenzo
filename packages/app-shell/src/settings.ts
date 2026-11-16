// What a person chooses about the shell, kept in this browser. Reads never throw: private browsing
// has no storage, and the default then applies.

const SINGLE_KEYS = 'lorenzo:single-keys';

/** Whether single-key shortcuts (G then a letter, ?) are on. They are, until switched off (WCAG 2.1.4). */
export function readSingleKeys(): boolean {
  try {
    return window.localStorage.getItem(SINGLE_KEYS) !== 'off';
  } catch {
    return true;
  }
}

export function writeSingleKeys(on: boolean): void {
  try {
    if (on) window.localStorage.removeItem(SINGLE_KEYS);
    else window.localStorage.setItem(SINGLE_KEYS, 'off');
  } catch {
    // Not kept; it applies until the page is closed.
  }
}
