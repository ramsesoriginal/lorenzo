import { agoText, appsByJob } from '@lorenzo/app-shell';
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
  loading,
  message,
} from '../../lib/dom';
import { recentPages } from '../../lib/recent';
import { appRegistry } from '../../lib/registry';
import { start } from '../../lib/session';

// A calendar as the list draws it: its name, and when it last changed.
function calendarCard(
  tenantId: string,
  calendar: { entity_id: string; name: string; updated_at: string },
) {
  const name = link(calendar.name, calendarHref(tenantId, calendar.entity_id));
  name.className = 'calendar-open';
  const title = el('h2', '', 'calendar-name');
  title.append(name);
  const top = el('div', '', 'row-tight');
  top.append(icon('kind-calendar', 'calendar-mark'), title);
  const changed = Date.parse(calendar.updated_at);
  const card = el('li', '', 'card card-body stack-tight calendar-card');
  card.append(
    top,
    el('p', Number.isNaN(changed) ? '' : `Last changed ${agoText(Date.now(), changed)}`, 'caption'),
  );

  return card;
}

// "Continue" (D16): what was open most lately in this library, if it is not the page itself.
function continueBlock(tenantId: string): HTMLElement | null {
  const recent = recentPages(tenantId);
  if (!recent.length) return null;
  const section = el('section', '', 'stack-tight home-label');
  section.setAttribute('aria-labelledby', 'home-continue');
  const title = el('h2', 'Continue');
  title.id = 'home-continue';
  const list = el('ul', '', 'home-tiles');
  const now = Date.now();
  for (const page of recent) {
    const open = el('a', '', 'card home-tile');
    open.href = page.href;
    const text = el('span', '', 'home-tile-text');
    text.append(
      el('b', page.title, 'home-tile-title'),
      el('span', page.at ? `Opened ${agoText(now, page.at)}` : 'Opened lately', 'caption'),
    );
    open.append(text);
    const item = el('li');
    item.append(open);
    list.append(item);
  }
  section.append(title, list);

  return section;
}

// "What do you want to do?" (D16): every deployed app, with what it is for.
function appsBlock(
  registry: NonNullable<Awaited<ReturnType<typeof appRegistry>>>,
): HTMLElement | null {
  const apps = appsByJob(registry).flatMap((job) => job.apps);
  if (!apps.length) return null;
  const section = el('section', '', 'stack-tight home-label');
  section.setAttribute('aria-labelledby', 'home-apps');
  const title = el('h2', 'What do you want to do?');
  title.id = 'home-apps';
  const list = el('ul', '', 'home-tiles home-tiles--apps');
  for (const app of apps) {
    const open = el('a', '', 'card home-tile');
    open.href = app.url;
    const text = el('span', '', 'home-tile-text');
    text.append(el('b', app.name, 'home-tile-title'), el('span', app.description, 'caption'));
    open.append(icon(app.icon, 'home-tile-icon'), text);
    const item = el('li');
    item.append(open);
    list.append(item);
  }
  section.append(title, list);

  return section;
}

export async function mount() {
  const host = document.querySelector<HTMLElement>('#CalendarList');
  if (!host || host.dataset.mounted) return;
  host.dataset.mounted = 'true';
  const session = await start();
  if (!session || !host.isConnected) return;

  const head = el('div', '', 'page-heading');
  const sub = el('p', `The calendars of ${session.tenantName}.`, 'page-sub');
  head.append(el('h1', 'Calendars'), sub);
  host.append(head);
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
      const list = el('ul', '', 'calendar-list');
      for (const calendar of calendars) {
        rememberEntryAddress(session.tenantId, calendar);
        list.append(calendarCard(session.tenantId, calendar));
      }
      host.append(list);
    } else
      host.append(
        emptyState(
          'No calendars here yet',
          session.canWrite
            ? 'Create one below to give a world its months, festivals and moons.'
            : 'No calendars in this library are available to you yet.',
          'empty-calendar',
        ),
      );
    if (session.canWrite) {
      const create = disclosure('Create a calendar', true);
      create.body.append(definitionEditor(session.tenantId));
      host.append(create.root);
      // The primary action of the page opens the form that makes one.
      const actions = el('div', '', 'page-heading-actions');
      const open = el('button', '', 'btn btn-primary');
      open.type = 'button';
      open.append(icon('add'), document.createTextNode('New calendar'));
      open.addEventListener('click', () => {
        create.root.open = true;
        create.root.scrollIntoView({ block: 'start' });
        create.body.querySelector<HTMLElement>('input, select, textarea')?.focus();
      });
      actions.append(open);
      // On the title's row, before the line under it.
      sub.before(actions);
    }
    const again = continueBlock(session.tenantId);
    if (again) host.append(again);
    void appRegistry().then((registry) => {
      const apps = registry ? appsBlock(registry) : null;
      if (apps && host.isConnected) host.append(apps);
    });
  } catch (e) {
    wait.replaceWith(failure(message(e)));
  }
}
