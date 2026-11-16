import { fill } from '@lorenzo/api-client';
import { client, unwrap } from './api';
import { el, icon } from './dom';
import { appRegistry } from './registry';

/**
 * Where an Event was presented (CS1): the Sessions whose played Scenes presented it. The API reads
 * a Session's play record and not an Event's, so each Session the person can see is asked; one whose
 * record is not theirs to read is left out, and nothing says it was there.
 */
export async function eventPresentations(
  tenantId: string,
  eventId: string,
): Promise<HTMLElement | null> {
  const template = (await appRegistry())?.links.session;
  if (!template) return null;
  const sessions = await client
    .GET('/tenants/{tenant_id}/sessions', { params: { path: { tenant_id: tenantId } } })
    .then(unwrap)
    .catch(() => []);
  const found: Array<{ session: { id: string; name: string }; scene: string; played: boolean }> =
    [];
  await Promise.all(
    sessions.map(async (session) => {
      const play = await client
        .GET('/tenants/{tenant_id}/sessions/{session_id}/play', {
          params: { path: { tenant_id: tenantId, session_id: session.id } },
        })
        .then((r) => r.data ?? null)
        .catch(() => null);
      if (!play) return;
      for (const presentation of play.presentations) {
        if (presentation.event_id !== eventId) continue;
        const appearance = play.appearances.find((a) => a.id === presentation.appearance_id);
        found.push({
          session,
          scene: appearance?.name ?? 'A Scene',
          played: appearance?.status === 'played',
        });
      }
    }),
  );
  if (!found.length) return null;
  const card = el('section', '', 'card card-body stack-tight');
  const list = el('ul', '', 'stack-tight');
  for (const row of found) {
    const item = el('li', '', 'row');
    const open = el('a', row.session.name);
    open.href = fill(template, { tenant: tenantId, id: row.session.id });
    item.append(
      icon('kind-session'),
      open,
      el('span', `${row.scene}${row.played ? '' : ' (not played)'}`, 'caption'),
    );
    list.append(item);
  }
  card.append(
    el('h2', 'Where it was presented'),
    el('p', 'Presented in a Scene says only that: it is not order, cause or knowledge.', 'caption'),
    list,
  );
  return card;
}
