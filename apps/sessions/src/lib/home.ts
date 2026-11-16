// What Home says of the Sessions a person has (CS1, screen 14): which one is next, which are past, and
// the Sessions of each campaign together. A pure module, so the page and its tests share it. A date
// is the real-world one; no in-world "now" is read from anywhere.
export type HomeSession = {
  tenant_id: string;
  id: string;
  name: string;
  slug?: string | null;
  campaign_id: string;
  real_date: string | null;
  can_manage: boolean;
};

export type State = 'past' | 'next' | null;

/** The Session to play next: the soonest dated today or later. Undated Sessions are never next. */
export function nextSession<T extends HomeSession>(
  sessions: readonly T[],
  today: string,
): T | undefined {
  return sessions
    .filter((s) => s.real_date !== null && s.real_date >= today)
    .sort((a, b) => (a.real_date as string).localeCompare(b.real_date as string))[0];
}

/** A Session's state on Home: past once its date has gone by, next for the one that is, else none. */
export function stateOf(session: HomeSession, today: string, next: HomeSession | undefined): State {
  if (session.real_date === null) return null;
  if (next && session.id === next.id) return 'next';
  return session.real_date < today ? 'past' : null;
}

export type Group<T extends HomeSession> = { tenant: string; campaign: string; sessions: T[] };

/** The Sessions of each campaign together, a campaign by its first Session's date, undated last. */
export function byCampaign<T extends HomeSession>(sessions: readonly T[]): Group<T>[] {
  const groups = new Map<string, Group<T>>();
  for (const s of sessions) {
    const key = `${s.tenant_id}|${s.campaign_id}`;
    const group = groups.get(key) ?? { tenant: s.tenant_id, campaign: s.campaign_id, sessions: [] };
    group.sessions.push(s);
    groups.set(key, group);
  }
  const order = (a: T, b: T) =>
    (a.real_date ?? '9999').localeCompare(b.real_date ?? '9999') || a.name.localeCompare(b.name);
  const list = [...groups.values()];
  for (const g of list) g.sessions.sort(order);
  return list.sort((a, b) => order(a.sessions[0] as T, b.sessions[0] as T));
}

/** "Thu 21 Mar", in the date's own day and never shifted by the reader's time zone. */
export function dateWords(iso: string | null): string {
  if (!iso) return 'Date not set';
  const day = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(day.getTime())) return iso;
  return day.toLocaleDateString('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    timeZone: 'UTC',
  });
}
