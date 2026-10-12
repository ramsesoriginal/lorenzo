// The three ways to look at a being (RFC 0043, docs/design/beings): Read, Play and Edit. A mode says
// what you are doing, not what you may do; the API still decides every write, and Edit is only
// offered to someone it would let write.

export type Mode = 'read' | 'play' | 'edit';

export const MODES: readonly { mode: Mode; label: string }[] = [
  { mode: 'read', label: 'Read' },
  { mode: 'play', label: 'Play' },
  { mode: 'edit', label: 'Edit' },
];

export type SheetSection = 'about' | 'notes' | 'stats' | 'inventory';

/** The mode to draw: Edit falls back to Read for someone who may not edit. */
export function effectiveMode(wanted: Mode, canEdit: boolean): Mode {
  return wanted === 'edit' && !canEdit ? 'read' : wanted;
}

/**
 * The order of the sections. Read puts the prose first and Play the numbers first; Edit follows
 * Read so the page does not jump when you start building the being.
 */
export function sectionOrder(mode: Mode): readonly SheetSection[] {
  return mode === 'play'
    ? ['stats', 'inventory', 'notes', 'about']
    : ['about', 'notes', 'stats', 'inventory'];
}

export function isMode(value: string | null | undefined): value is Mode {
  return value === 'read' || value === 'play' || value === 'edit';
}
