import { rememberEntryAddress } from '../../lib/addresses';
import { client, fetchAllPages, unwrap } from '../../lib/api';
import { definitionEditor } from '../../lib/definition-editor';
import { calendarHref, el, link, message } from '../../lib/dom';
import { start } from '../../lib/session';
export async function mount() {
  const host = document.querySelector<HTMLElement>('#CalendarList');
  if (!host || host.dataset.mounted) return;
  host.dataset.mounted = 'true';
  const session = await start();
  if (!session || !host.isConnected) return;

  host.append(
    el('h1', 'Calendars'),
    link('Browse Events', `/events/?tenant=${encodeURIComponent(session.tenantId)}`),
    el('p', 'Choose a calendar to explore its dates, notes and story events.', 'intro'),
  );
  const status = el('p');
  status.setAttribute('role', 'status');
  host.append(status);
  try {
    const calendars = await fetchAllPages(async (page) =>
      unwrap(
        await client.GET('/tenants/{tenant_id}/calendars', {
          params: { path: { tenant_id: session.tenantId }, query: { page, size: 100 } },
        }),
      ),
    );
    if (!host.isConnected) return;
    const list = el('ul', '', 'calendar-list');
    for (const calendar of calendars) {
      rememberEntryAddress(session.tenantId, calendar);
      const item = el('li', '', 'panel');
      const open = link(calendar.name, calendarHref(session.tenantId, calendar.entity_id));
      open.className = 'calendar-card';
      item.append(open);
      list.append(item);
    }
    host.append(list);
    if (!calendars.length)
      host.append(el('p', 'There are no calendars available to you in this library yet.'));
    if (session.canWrite) {
      const create = el('details');
      create.append(el('summary', 'Create a calendar'), definitionEditor(session.tenantId));
      host.append(create);
    }
  } catch (e) {
    status.textContent = message(e);
  }
}
