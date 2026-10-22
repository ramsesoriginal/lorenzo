import { renderAudienceControl } from '@lorenzo/information-editor';
import { canonicalAddress, rememberEntryAddress, resolveAddress } from '../../lib/addresses';
import { client, unwrap } from '../../lib/api';
import { clockRelationships, eventClockConversions } from '../../lib/clock-ratios';
import { clockPanel, eventReadings } from '../../lib/clocks';
import { datedEntries, recurrenceFields } from '../../lib/dated-entries';
import {
  button,
  calendarHref,
  disclosure,
  el,
  entryHref,
  failure,
  feedback,
  field,
  iconLink,
  link,
  linkButton,
  loading,
  message,
} from '../../lib/dom';
import { eventOrder } from '../../lib/event-order';
import { eventVisibility } from '../../lib/event-visibility';
import { informationForm, informationView } from '../../lib/information';
import { eventLearning, learningList } from '../../lib/learning';
import { participants } from '../../lib/participants';
import { start } from '../../lib/session';

const kindNames: Partial<Record<string, string>> = {
  calendar_period: 'Calendar period',
  event: 'Story event',
  fact: 'Canonical fact',
  observance: 'Recurring observance',
  calendar: 'Calendar',
  clock: 'Clock',
};

export async function mount() {
  const host = document.querySelector<HTMLElement>('#EntryView');
  if (!host || host.dataset.mounted) return;
  host.dataset.mounted = 'true';
  const session = await start();
  if (!session || !host.isConnected) return;
  const { tenantId } = session;
  let canWrite = session.canWrite;
  const crumbs = el('div', '', 'row');
  crumbs.append(
    iconLink('All calendars', `/?tenant=${encodeURIComponent(tenantId)}`, 'back'),
    iconLink('All Events', `/events/?tenant=${encodeURIComponent(tenantId)}`, 'kind-event'),
  );
  const wait = loading('Loading entry…');
  host.append(crumbs, wait);
  try {
    const params = new URLSearchParams(location.search);
    const id = await resolveAddress(tenantId, params);
    const path = { tenant_id: tenantId, entity_id: id };
    const result = await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
      params: { path },
    });
    const entry = await unwrap(result);
    const access = await unwrap(
      await client.GET('/tenants/{tenant_id}/entities/{entity_id}/access', { params: { path } }),
    );
    canWrite = access.can_edit;
    if (!host.isConnected) return;
    rememberEntryAddress(tenantId, entry);
    canonicalAddress(tenantId, id);
    const version = result.response.headers.get('etag');
    const head = el('div', '', 'stack-tight');
    const kinds = el('div', '', 'row-tight kinds');
    for (const kind of entry.kinds) kinds.append(el('span', kindNames[kind] ?? kind, 'badge'));
    head.append(el('h1', entry.name), kinds);
    wait.replaceWith(head);
    const actions = el('div', '', 'row');
    if (entry.kinds.includes('calendar'))
      actions.append(
        linkButton('Browse this calendar', calendarHref(tenantId, id), 'kind-calendar'),
      );
    if (entry.kinds.includes('calendar_period')) {
      const calendar = params.get('calendar');
      const year = params.get('year');
      if (calendar)
        actions.append(
          linkButton(
            'Back to calendar',
            calendarHref(tenantId, calendar, year === null ? undefined : Number(year)),
            'back',
          ),
        );
    }
    if (actions.childElementCount) host.append(actions);
    if (entry.kinds.includes('clock')) {
      host.append(await clockPanel(tenantId, id, session.canOrderEvents));
      host.append(await clockRelationships(tenantId, id, entry.name));
    }
    if (entry.kinds.includes('event')) {
      host.append(await eventReadings(tenantId, id));
      host.append(await eventClockConversions(tenantId, id));
    }
    if (entry.kinds.includes('calendar_period')) host.append(await datedEntries(tenantId, id));
    if (entry.kinds.includes('event') && session.canReadEventOrder) {
      try {
        const ordering = await eventOrder(tenantId, id, session.canOrderEvents);
        if (ordering) host.append(ordering);
        if (canWrite) host.append(await participants(tenantId, id, session.canOrderEvents));
        if (session.canOrderEvents) host.append(await eventLearning(tenantId, id));
      } catch (error) {
        host.append(failure(`Could not load Event ordering. ${message(error)}`));
      }
    }
    if (entry.kinds.includes('being') && session.canOrderEvents) {
      const learning = el('section', '', 'card card-body stack');
      learning.append(
        el('h2', 'Recorded learning'),
        await learningList(tenantId, { being_id: id }),
      );
      host.append(learning);
    }
    const refresh = () => {
      if (host.isConnected) location.reload();
    };
    if (canWrite && entry.kinds.includes('event'))
      host.append(await eventVisibility(tenantId, id, refresh));
    if (canWrite) {
      const controls = disclosure('Name, link name and audience', true);
      const status = feedback();
      const name = field('Entry name', entry.name);
      const slug = field('Link name', entry.slug ?? '');
      const saveName = el('div', '', 'row');
      saveName.append(
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
              status.fail(`${message(e)} Your name draft is kept.`);
            }
          },
          true,
        ),
      );
      const saveSlug = el('div', '', 'row');
      saveSlug.append(
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
              const next = await unwrap(
                await client.GET('/tenants/{tenant_id}/entities/{entity_id}', { params: { path } }),
              );
              rememberEntryAddress(tenantId, next);
              canonicalAddress(tenantId, id);
              refresh();
            } catch (e) {
              status.fail(`${message(e)} Your link-name draft is kept.`);
            }
          },
          true,
        ),
      );
      controls.body.append(
        name.label,
        saveName,
        slug.label,
        saveSlug,
        status.node,
        renderAudienceControl({
          client,
          tenantId,
          entityId: id,
          allowParticipants: entry.kinds.includes('event'),
        }),
      );
      host.append(controls.root);
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
      const rule = el('section', '', 'card card-body stack-tight');
      rule.append(
        iconLink(calendar.name, calendarHref(tenantId, obs.calendar_entity_id), 'kind-calendar'),
        el(
          'p',
          `${obs.rule.day} ${calendar.definition.segments.find((s) => s.key === obs.rule.segment)?.name ?? obs.rule.segment}, every ${obs.rule.when.every} year(s), offset ${obs.rule.when.offset}. Absent dates are skipped.`,
        ),
      );
      host.append(rule);
      if (canWrite) {
        const edit = disclosure('Edit recurrence', true);
        const status = feedback();
        const rules = recurrenceFields(calendar.definition, obs.rule);
        const actions = el('div', '', 'row');
        actions.append(
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
                status.fail(
                  `${message(e)} Your rule draft is kept; reload the saved entry before retrying.`,
                );
              }
            },
            true,
          ),
        );
        edit.body.append(rules.element, actions, status.node);
        host.append(edit.root);
      }
    }
    if (entry.kinds.includes('fact') || entry.kinds.includes('event')) {
      const dates = await unwrap(
        await client.GET('/tenants/{tenant_id}/entities/{entity_id}/dates', { params: { path } }),
      );
      const section = el('section', '', 'stack-tight');
      const status = feedback();
      const head = el('div', '', 'section-head');
      head.append(el('h2', 'Dates'));
      section.append(
        head,
        el(
          'p',
          'These are calendar associations. They do not establish causal or lived order.',
          'caption',
        ),
      );
      host.append(section);
      const list = el('ul', '', 'list');
      for (const date of dates) {
        const row = el('li', '', 'row');
        const name = link(
          date.name,
          `${entryHref(tenantId, date.entity_id)}&calendar=${encodeURIComponent(date.calendar_entity_id)}&year=${date.year}`,
        );
        name.classList.add('grow');
        row.append(
          name,
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
                  status.fail(`${message(e)} The date list has not been replaced.`);
                }
              },
              true,
              'close',
            ),
          );
        list.append(row);
      }
      if (dates.length) section.append(list);
      else
        section.append(
          el(
            'p',
            canWrite
              ? 'This entry has no date yet. Open a day in a calendar and choose it there.'
              : 'No dates are available to you for this entry.',
            'lede',
          ),
        );
      if (canWrite && dates.length)
        section.append(
          el(
            'p',
            'To associate another date, open it in a calendar and choose this existing entry.',
            'caption',
          ),
        );
      section.append(status.node);
    }
    if (entry.kinds.includes('fact')) {
      const subjects = await unwrap(
        await client.GET('/tenants/{tenant_id}/entities/{entity_id}/about', { params: { path } }),
      );
      const about = el('section', '', 'stack-tight');
      const head = el('div', '', 'section-head');
      head.append(el('h2', 'About'));
      about.append(head);
      const list = el('ul', '', 'stack-tight');
      for (const subject of subjects) {
        const item = el('li');
        item.append(link(subject.name, entryHref(tenantId, subject.id)));
        list.append(item);
      }
      if (subjects.length) about.append(list);
      else about.append(el('p', 'No subjects are available to you.', 'lede'));
      host.append(about);
    }
    host.append(
      informationView(tenantId, entry, canWrite, refresh, session.canOrderEvents, access),
    );
    if (access.can_add_notes && params.get('add') === 'information') {
      const frame = el('div', '', 'card card-body');
      frame.dataset.formFrame = '';
      frame.append(informationForm(tenantId, id, refresh));
      host.append(frame);
    }
  } catch (e) {
    const problem = failure(message(e));
    if (wait.isConnected) wait.replaceWith(problem);
    else host.append(problem);
  }
}
