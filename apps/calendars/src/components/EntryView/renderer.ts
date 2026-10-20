import { renderAudienceControl } from '@lorenzo/information-editor';
import { client, unwrap } from '../../lib/api';
import { datedEntries, recurrenceFields } from '../../lib/dated-entries';
import { button, calendarHref, el, entryHref, field, link, message } from '../../lib/dom';
import { eventOrder } from '../../lib/event-order';
import { informationForm, informationView } from '../../lib/information';
import { start } from '../../lib/session';
export async function mount() {
  const session = await start();
  if (!session) return;
  const { tenantId, canWrite } = session;
  const host = document.querySelector('#EntryView');
  if (!host) return;
  const status = el('p');
  status.setAttribute('role', 'status');
  host.append(link('All calendars', `/?tenant=${encodeURIComponent(tenantId)}`), status);
  try {
    const params = new URLSearchParams(location.search);
    const id = params.get('id');
    if (!id) throw new Error('Choose an entry from a calendar.');
    const path = { tenant_id: tenantId, entity_id: id };
    const result = await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
      params: { path },
    });
    const entry = await unwrap(result);
    const version = result.response.headers.get('etag');
    host.append(
      el('h1', entry.name),
      el(
        'p',
        entry.kinds
          .map(
            (k) =>
              (
                ({
                  calendar_period: 'Calendar period',
                  event: 'Story event',
                  fact: 'Canonical fact',
                  observance: 'Recurring observance',
                  calendar: 'Calendar',
                }) as Partial<Record<string, string>>
              )[k] ?? k,
          )
          .join(' · '),
        'caption',
      ),
    );
    if (entry.kinds.includes('calendar'))
      host.append(link('Browse this calendar', calendarHref(tenantId, id)));
    if (entry.kinds.includes('calendar_period')) {
      const calendar = params.get('calendar');
      const year = params.get('year');
      if (calendar)
        host.append(
          link(
            'Back to calendar',
            calendarHref(tenantId, calendar, year === null ? undefined : Number(year)),
          ),
        );
      host.append(await datedEntries(tenantId, id));
    }
    if (entry.kinds.includes('event') && session.canOrderEvents) {
      try {
        const ordering = await eventOrder(tenantId, id);
        if (ordering) host.append(ordering);
      } catch (error) {
        host.append(el('p', `Could not load Event ordering. ${message(error)}`, 'caption'));
      }
    }
    const refresh = () => location.reload();
    if (canWrite) {
      const controls = el('details');
      controls.append(el('summary', 'Name, link name and audience'));
      const name = field('Entry name', entry.name);
      const slug = field('Link name', entry.slug ?? '');
      controls.append(
        name.label,
        button(
          'Save name',
          async () => {
            try {
              await unwrap(
                await client.PATCH('/tenants/{tenant_id}/entities/{entity_id}', {
                  params: { path, header: { 'if-match': version ?? '' } },
                  body: { name: name.input.value },
                }),
              );
              refresh();
            } catch (e) {
              status.textContent = `${message(e)} Your name draft is kept.`;
            }
          },
          true,
        ),
        slug.label,
        button(
          'Save link name',
          async () => {
            try {
              if (slug.input.value)
                await unwrap(
                  await client.PUT('/tenants/{tenant_id}/entities/{entity_id}/slug', {
                    params: { path },
                    body: { slug: slug.input.value },
                  }),
                );
              else
                await unwrap(
                  await client.DELETE('/tenants/{tenant_id}/entities/{entity_id}/slug', {
                    params: { path },
                  }),
                );
              refresh();
            } catch (e) {
              status.textContent = `${message(e)} Your link-name draft is kept.`;
            }
          },
          true,
        ),
        renderAudienceControl({ client, tenantId, entityId: id }),
      );
      host.append(controls);
    }
    if (entry.kinds.includes('observance')) {
      const obs = await unwrap(
        await client.GET('/tenants/{tenant_id}/observances/{entity_id}', { params: { path } }),
      );
      const calendar = await unwrap(
        await client.GET('/tenants/{tenant_id}/calendars/{entity_id}', {
          params: { path: { tenant_id: tenantId, entity_id: obs.calendar_entity_id } },
        }),
      );
      host.append(
        link(calendar.name, calendarHref(tenantId, obs.calendar_entity_id)),
        el(
          'p',
          `${obs.rule.day} ${calendar.definition.segments.find((s) => s.key === obs.rule.segment)?.name ?? obs.rule.segment}, every ${obs.rule.when.every} year(s), offset ${obs.rule.when.offset}. Absent dates are skipped.`,
        ),
      );
      if (canWrite) {
        const edit = el('details');
        edit.append(el('summary', 'Edit recurrence'));
        const rules = recurrenceFields(calendar.definition, obs.rule);
        edit.append(
          rules.element,
          button(
            'Save recurrence',
            async () => {
              try {
                await unwrap(
                  await client.PUT('/tenants/{tenant_id}/observances/{entity_id}/rule', {
                    params: { path, header: { 'if-match': version ?? '' } },
                    body: rules.read(),
                  }),
                );
                refresh();
              } catch (e) {
                status.textContent = `${message(e)} Your rule draft is kept; reload the saved entry before retrying.`;
              }
            },
            true,
          ),
        );
        host.append(edit);
      }
    }
    if (entry.kinds.includes('fact') || entry.kinds.includes('event')) {
      const dates = await unwrap(
        await client.GET('/tenants/{tenant_id}/entities/{entity_id}/dates', { params: { path } }),
      );
      const section = el('section', '', 'stack-tight');
      section.append(
        el('h2', 'Dates'),
        el(
          'p',
          'These are calendar associations. They do not establish causal or lived order.',
          'caption',
        ),
      );
      host.append(section);
      for (const date of dates) {
        const row = el('div', '', 'row');
        row.append(
          link(
            date.name,
            `${entryHref(tenantId, date.entity_id)}&calendar=${encodeURIComponent(date.calendar_entity_id)}&year=${date.year}`,
          ),
          link('Calendar', calendarHref(tenantId, date.calendar_entity_id, date.year)),
        );
        if (canWrite)
          row.append(
            button(
              'Remove date association',
              async () => {
                try {
                  await unwrap(
                    await client.PUT('/tenants/{tenant_id}/entities/{entity_id}/dates', {
                      params: { path, header: { 'if-match': version ?? '' } },
                      body: {
                        period_ids: dates
                          .filter((d) => d.entity_id !== date.entity_id)
                          .map((d) => d.entity_id),
                      },
                    }),
                  );
                  refresh();
                } catch (e) {
                  status.textContent = `${message(e)} The date list has not been replaced.`;
                }
              },
              true,
            ),
          );
        section.append(row);
      }
      if (!dates.length) section.append(el('p', 'No dates are available to you for this entry.'));
      if (canWrite)
        section.append(
          el(
            'p',
            'To associate another date, open it in a calendar and choose this existing entry.',
            'caption',
          ),
        );
    }
    if (entry.kinds.includes('fact')) {
      const subjects = await unwrap(
        await client.GET('/tenants/{tenant_id}/entities/{entity_id}/about', { params: { path } }),
      );
      const about = el('section', '', 'stack-tight');
      about.append(el('h2', 'About'));
      for (const subject of subjects)
        about.append(link(subject.name, entryHref(tenantId, subject.id)));
      if (!subjects.length) about.append(el('p', 'No subjects are available to you.', 'caption'));
      host.append(about);
    }
    host.append(informationView(tenantId, entry, canWrite, refresh));
    if (canWrite && params.get('add') === 'information')
      host.append(informationForm(tenantId, id, refresh));
  } catch (e) {
    status.textContent = message(e);
  }
}
