import { rememberEntryAddress } from '../../lib/addresses';
import { client, fetchAllPages, unwrap } from '../../lib/api';
import { definitionEditor } from '../../lib/definition-editor';
import {
  calendarHref,
  disclosure,
  el,
  emptyState,
  failure,
  icon,
  link,
  linkButton,
  loading,
  message,
} from '../../lib/dom';
import { start } from '../../lib/session';

export async function mount() {
  const host = document.querySelector<HTMLElement>('#CalendarList');
  if (!host || host.dataset.mounted) return;
  host.dataset.mounted = 'true';
  const session = await start();
  if (!session || !host.isConnected) return;

  const head = el('div', '', 'page-header');
  head.append(
    el('h1', 'Calendars'),
    linkButton(
      'Browse clocks',
      `/clocks/?tenant=${encodeURIComponent(session.tenantId)}`,
      'kind-clock',
    ),
    linkButton(
      'Browse Events',
      `/events/?tenant=${encodeURIComponent(session.tenantId)}`,
      'kind-event',
    ),
  );
  const top = el('div', '', 'stack-tight');
  top.append(head, el('p', 'Choose a calendar to read its dates, notes and Events.', 'lede'));
  host.append(top);
  const wait = loading('Loading calendars…');
  host.append(wait);
  try {
    const calendars = await fetchAllPages(async (page) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/calendars', {
          params: { path: { tenant_id: session.tenantId }, query: { page, size: 100 } },
        }),
      ),
    );
    if (!host.isConnected) return;
    wait.remove();
    if (calendars.length) {
      const list = el('ul', '', 'grid calendar-list');
      for (const calendar of calendars) {
        rememberEntryAddress(session.tenantId, calendar);
        const open = link(calendar.name, calendarHref(session.tenantId, calendar.entity_id));
        open.className = 'card calendar-card';
        open.replaceChildren(
          icon('kind-calendar', 'calendar-mark'),
          el('span', calendar.name, 'calendar-name'),
          icon('next'),
        );
        const item = el('li');
        item.append(open);
        list.append(item);
      }
      host.append(list);
    } else
      host.append(
        emptyState(
          'No calendars here yet',
          session.canWrite
            ? 'Create one below to give a world its months, festivals and moons.'
            : 'No calendars in this library are available to you yet.',
        ),
      );
    if (session.canWrite) {
      const create = disclosure('Create a calendar', true);
      create.body.append(definitionEditor(session.tenantId));
      host.append(create.root);
    }
  } catch (e) {
    wait.replaceWith(failure(message(e)));
  }
}
