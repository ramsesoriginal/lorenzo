import { client, fetchAllPages, unwrap } from '../../lib/api';
import { definitionEditor } from '../../lib/definition-editor';
import { calendarHref, el, link, message } from '../../lib/dom';
import { start } from '../../lib/session';
export async function mount() {
  const session = await start();
  if (!session) return;
  const host = document.querySelector('#CalendarList');
  if (!host) return;
  host.append(
    el('h1', 'Calendars'),
    el('p', 'The reckonings your worlds use. Open any year; add detail where your story needs it.'),
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
    const list = el('ul', '', 'calendar-list');
    for (const calendar of calendars) {
      const item = el('li', '', 'panel');
      item.append(link(calendar.name, calendarHref(session.tenantId, calendar.entity_id)));
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
