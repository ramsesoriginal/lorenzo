/**
 * The character or group last opened on each library's board, in this browser (ADR 0134),
 * so the board opens on it again. The URL always wins: this only fills in for it. Kept per
 * library, and forgotten on log out, like the last library (lastTenant.ts).
 */
export const LAST_HOLDER_KEY = 'lorenzo:lastHolder';

export type Holder = Readonly<{ kind: 'character' | 'group'; id: string }>;

// localStorage can throw (private browsing, disabled) - then nothing is
// remembered, and the board behaves as if it never was.

function remembered(): Record<string, Holder> {
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(LAST_HOLDER_KEY) ?? '{}');
    return parsed !== null && typeof parsed === 'object' ? (parsed as Record<string, Holder>) : {};
  } catch {
    return {};
  }
}

export function getLastHolder(tenantId: string): Holder | null {
  const holder = remembered()[tenantId];
  const valid =
    holder !== undefined &&
    (holder.kind === 'character' || holder.kind === 'group') &&
    typeof holder.id === 'string';
  return valid ? holder : null;
}

export function rememberHolder(tenantId: string, holder: Holder): void {
  try {
    window.localStorage.setItem(
      LAST_HOLDER_KEY,
      JSON.stringify({ ...remembered(), [tenantId]: holder }),
    );
  } catch {
    // Nothing remembered, then.
  }
}

export function forgetHolders(): void {
  try {
    window.localStorage.removeItem(LAST_HOLDER_KEY);
  } catch {
    // Nothing was remembered either.
  }
}

/**
 * Which of `holders` the board opens when the URL names none: the one last opened, if it's
 * still among them, else the only character, if there's exactly one.
 */
export function defaultHolder(holders: readonly Holder[], last: Holder | null): Holder | null {
  if (last && holders.some((h) => h.kind === last.kind && h.id === last.id)) return last;
  const characters = holders.filter((h) => h.kind === 'character');
  return characters.length === 1 ? (characters[0] ?? null) : null;
}
