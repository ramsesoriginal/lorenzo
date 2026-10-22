import { rememberEntryAddress, tenantAddress } from '../../lib/addresses';
import { client, unwrap } from '../../lib/api';
import {
  button,
  disclosure,
  el,
  entryHref,
  feedback,
  field,
  iconLink,
  link,
  message,
  select,
  submit,
} from '../../lib/dom';
import { entryPicker } from '../../lib/entry-picker';
import { creationVisibility } from '../../lib/event-visibility';
import { start } from '../../lib/session';

export async function mount() {
  const host = document.querySelector<HTMLElement>('#EventList');
  if (!host || host.dataset.mounted) return;
  host.dataset.mounted = 'true';
  const session = await start();
  if (!session || !host?.isConnected) return;
  const { tenantId, canOrderEvents, canReadEventOrder } = session;
  const initial = new URLSearchParams(location.search);
  let being = canOrderEvents ? (initial.get('being') ?? '') : '';
  let chain = initial.get('chain') ?? '';
  let page = 1;
  const top = el('div', '', 'stack-tight');
  top.append(
    el('h1', 'Events'),
    el('p', 'Record what happened, even before its date is known.', 'lede'),
  );
  host.append(iconLink('All calendars', `/?tenant=${encodeURIComponent(tenantId)}`, 'back'), top);
  const status = feedback();
  const list = el('ol', '', 'list');
  list.dataset.eventList = '';
  const nav = el('div', '', 'row');
  const q = field('Search Event names', initial.get('q') ?? '');
  const sort = select(
    'List order',
    canReadEventOrder
      ? [
          ['name', 'Name'],
          ['order', 'Story order'],
        ]
      : [['name', 'Name']],
    canReadEventOrder && initial.get('sort') === 'order' ? 'order' : 'name',
  );
  sort.input.setAttribute('aria-label', 'List order');
  const direction = select(
    'Causal direction',
    [
      ['both', 'What led here and followed'],
      ['ancestors', 'What led here'],
      ['descendants', 'What followed'],
    ],
    'both',
  );
  direction.input.setAttribute('aria-label', 'Causal direction');
  const filters = el('div', '', 'card card-body stack');
  const choices = el('p', '', 'caption');
  function showChoices() {
    choices.textContent = [
      being ? 'Participant filter selected' : '',
      chain ? 'Causal Event selected' : '',
    ]
      .filter(Boolean)
      .join(' · ');
  }
  let generation = 0;
  async function load() {
    const turn = ++generation;
    status.busy('Loading Events…');
    try {
      const response = await unwrap(
        await client.GET('/tenants/{tenant_id}/events', {
          params: {
            path: { tenant_id: tenantId },
            query: {
              q: q.input.value,
              sort: sort.input.value as 'name' | 'order',
              being_id: being || undefined,
              causal_event_id: chain || undefined,
              direction: direction.input.value as 'both' | 'ancestors' | 'descendants',
              page,
              size: 30,
            },
          },
        }),
      );
      if (turn !== generation || !host?.isConnected) return;
      list.replaceChildren();
      list.hidden = !response.items.length;
      list.start = (page - 1) * 30 + 1;
      for (const entry of response.items) {
        rememberEntryAddress(tenantId, entry);
        const row = el('li');
        const open = link(entry.name, entryHref(tenantId, entry.entity_id));
        open.classList.add('grow');
        row.append(open);
        if (entry.order_basis)
          row.append(
            el(
              'span',
              {
                causal: 'Causal order',
                ruled: 'Recorded order',
                linearized: canOrderEvents
                  ? 'Linearized · no recorded ordering path'
                  : 'Linearized · no visible recorded ordering path',
              }[entry.order_basis],
              'caption',
            ),
          );
        if (canReadEventOrder)
          row.append(
            button(
              'Follow causes',
              () => {
                chain = entry.entity_id;
                sort.input.value = 'order';
                page = 1;
                showChoices();
                void load();
              },
              true,
              'causality',
            ),
          );
        list.append(row);
      }
      nav.replaceChildren();
      if (page > 1)
        nav.append(
          button(
            'Previous Events',
            () => {
              page--;
              void load();
            },
            true,
            'previous',
          ),
        );
      if (page < (response.pages ?? 0))
        nav.append(
          button(
            'Next Events',
            () => {
              page++;
              void load();
            },
            true,
            'next',
          ),
        );
      status.say(
        response.total
          ? `${response.total} Event${response.total === 1 ? '' : 's'}.`
          : 'No Events match these filters.',
      );
      const address = new URL(location.href);
      address.searchParams.set('tenant', tenantAddress(tenantId));
      for (const [key, value] of Object.entries({
        q: q.input.value,
        sort: sort.input.value,
        being,
        chain,
      })) {
        if (value) address.searchParams.set(key, value);
        else address.searchParams.delete(key);
      }
      history.replaceState(history.state, '', address);
    } catch (error) {
      if (turn === generation) {
        list.replaceChildren();
        list.hidden = true;
        status.fail(message(error));
      }
    }
  }
  const bar = el('div', '', 'toolbar');
  bar.append(
    q.label,
    sort.label,
    button(
      'Find Events',
      () => {
        page = 1;
        void load();
      },
      false,
      'search',
    ),
  );
  filters.append(bar);
  if (canReadEventOrder) {
    const advanced = disclosure(canOrderEvents ? 'Participants and causes' : 'Causes');
    advanced.body.append(
      ...(canOrderEvents
        ? [
            entryPicker(tenantId, 'Filter by being', 'being', (entry) => {
              being = entry.id;
              page = 1;
              showChoices();
              void load();
            }),
          ]
        : []),
      entryPicker(tenantId, 'Follow an Event', 'event', (entry) => {
        chain = entry.id;
        page = 1;
        showChoices();
        void load();
      }),
      direction.label,
      choices,
      button(
        canOrderEvents ? 'Clear participant and causal filters' : 'Clear causal filter',
        () => {
          being = '';
          chain = '';
          page = 1;
          showChoices();
          void load();
        },
        true,
        'close',
      ),
    );
    filters.append(advanced.root);
  }
  if (session.canCreateEntries) {
    const create = disclosure('Create an Event', true);
    const form = el('form', '', 'stack');
    const name = field('Event name');
    name.input.required = true;
    const visibility = creationVisibility();
    const kind = select(
      'Entry kind',
      [
        ['event', 'Event'],
        ['fact', 'Fact'],
      ],
      'event',
    );
    const save = submit('Create Event');
    kind.input.addEventListener('change', () => {
      save.textContent = kind.input.value === 'event' ? 'Create Event' : 'Create Fact';
      visibility.setEvent(kind.input.value === 'event');
    });
    const progress = feedback();
    const id = crypto.randomUUID();
    const actions = el('div', '', 'row');
    actions.append(save);
    form.append(
      name.label,
      kind.label,
      visibility.label,
      el('p', 'Starts undated. Notes have their own audiences.', 'caption'),
      actions,
      progress.node,
    );
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      save.disabled = true;
      progress.busy('Creating…');
      try {
        await unwrap(
          await client.POST('/tenants/{tenant_id}/entities', {
            params: { path: { tenant_id: tenantId } },
            body: {
              id,
              name: name.input.value,
              kinds: [kind.input.value as 'event' | 'fact'],
              visibility: visibility.value(),
              parents: [],
            },
          }),
        );
        if (form.isConnected) location.assign(entryHref(tenantId, id));
      } catch (error) {
        try {
          const existing = await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
            params: { path: { tenant_id: tenantId, entity_id: id } },
          });
          if (existing.data?.kinds.includes(kind.input.value as 'event' | 'fact')) {
            if (form.isConnected) location.assign(entryHref(tenantId, id));
            return;
          }
        } catch {
          /* Keep the stable retry identity and draft. */
        }
        progress.fail(`${message(error)} Your draft is kept.`);
        save.disabled = false;
      }
    });
    create.body.append(form);
    host.append(create.root);
  }
  host.append(
    filters,
    el(
      'p',
      canOrderEvents
        ? 'Story order follows recorded relationships. Linearized placements supply no evidence of chronology. Causal filters follow causes, including branches.'
        : 'Your story order uses shared relationships between Events you can see. Linearized placements are display order, not evidence of chronology. Other readers may see a different order.',
      'caption',
    ),
    status.node,
    list,
    nav,
  );
  showChoices();
  await load();
}
