// The two modes of a being's page (BN2, docs/design/web/beings): Read and Play. A mode says what
// you are doing, not what you may do; the API still decides every write. There is no Edit mode:
// a section a person may change has its own edit control, and saves on its own.

export type Mode = 'read' | 'play';

export const MODES: readonly { mode: Mode; label: string }[] = [
  { mode: 'read', label: 'Read' },
  { mode: 'play', label: 'Play' },
];

export type SheetSection = 'about' | 'notes' | 'stats' | 'inventory';

/** What each mode is for, said on the band (BN7). */
export const MODE_LINES: Record<Mode, string> = {
  read: 'Reading. Edit a section where it is.',
  play: 'At the table. Numbers first; every change can be undone.',
};

const memoryKey = (tenantId: string, entityId: string) =>
  `lorenzo:beings:mode:${tenantId}:${entityId}`;

/**
 * The mode last used on this being in this browser (BN5), so whoever plays it lands in Play at the
 * table. Storage can throw (private browsing, disabled): then nothing is remembered.
 */
export function savedMode(tenantId: string, entityId: string): Mode {
  try {
    const saved = window.localStorage.getItem(memoryKey(tenantId, entityId));

    return saved === 'play' ? 'play' : 'read';
  } catch {
    return 'read';
  }
}

export function rememberMode(tenantId: string, entityId: string, mode: Mode): void {
  try {
    window.localStorage.setItem(memoryKey(tenantId, entityId), mode);
  } catch {
    // The page opens in Read next time.
  }
}

/** The order of the sections. Read puts the prose first and Play the numbers first. */
export function sectionOrder(mode: Mode): readonly SheetSection[] {
  return mode === 'play'
    ? ['stats', 'inventory', 'notes', 'about']
    : ['about', 'notes', 'stats', 'inventory'];
}

export function isMode(value: string | null | undefined): value is Mode {
  return value === 'read' || value === 'play';
}

/** How densely a being is drawn: as a sheet, or as a datasheet (a stat line, a weapons table, abilities). */
export type Layout = 'sheet' | 'datasheet';

export const LAYOUTS: readonly { layout: Layout; label: string }[] = [
  { layout: 'sheet', label: 'Sheet' },
  { layout: 'datasheet', label: 'Datasheet' },
];

export function isLayout(value: string | null | undefined): value is Layout {
  return value === 'sheet' || value === 'datasheet';
}
