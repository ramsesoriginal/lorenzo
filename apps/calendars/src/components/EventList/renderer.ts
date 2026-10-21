import { rememberEntryAddress, tenantAddress } from '../../lib/addresses';
import { client, unwrap } from '../../lib/api';
import { button, el, entryHref, field, link, message, select } from '../../lib/dom';
import { entryPicker } from '../../lib/entry-picker';
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
  host.append(
    link('All calendars', `/?tenant=${encodeURIComponent(tenantId)}`),
    el('h1', 'Events'),
    el('p', 'Record what happened, even before its date is known.', 'intro'),
  );
  const status = el('p');
  status.setAttribute('role', 'status');
  const list = el('ol', '', 'stack');
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
  const filters = el('div', '', 'stack-tight');
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
    status.textContent = 'Loading Events…';
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
      list.start = (page - 1) * 30 + 1;
      for (const entry of response.items) {
        rememberEntryAddress(tenantId, entry);
        const row = el('li', '', 'panel stack-tight');
        row.append(link(entry.name, entryHref(tenantId, entry.entity_id)));
        if (entry.order_basis)
          row.append(
            el(
              'p',
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
          ),
        );
      status.textContent = response.total
        ? `${response.total} Event${response.total === 1 ? '' : 's'}.`
        : 'No Events match these filters.';
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
        status.textContent = message(error);
      }
    }
  }
  filters.append(
    q.label,
    sort.label,
    button(
      'Find Events',
      () => {
        page = 1;
        void load();
      },
      true,
    ),
  );
  if (canReadEventOrder) {
    const advanced = el('details', '', 'panel');
    const body = el('div', '', 'stack');
    advanced.append(el('summary', canOrderEvents ? 'Participants and causes' : 'Causes'), body);
    body.append(
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
      ),
    );
    filters.append(advanced);
  }
  if (session.canCreateEntries) {
    const create = el('details', '', 'panel');
    create.append(el('summary', 'Create an Event'));
    const form = el('form', '', 'stack');
    const name = field('Event name');
    name.input.required = true;
    const kind = el('select');
    kind.setAttribute('aria-label', 'Entry kind');
    for (const [value, label] of [
      ['event', 'Event'],
      ['fact', 'Fact'],
    ]) {
      const option = el('option', label);
      option.value = value;
      kind.append(option);
    }
    const kindLabel = el('label', 'Entry kind');
    kindLabel.append(kind);
    const save = el('button', 'Create Event', 'btn');
    save.type = 'submit';
    kind.addEventListener('change', () => {
      save.textContent = kind.value === 'event' ? 'Create Event' : 'Create Fact';
    });
    const progress = el('p');
    progress.setAttribute('role', 'status');
    const id = crypto.randomUUID();
    form.append(
      name.label,
      kindLabel,
      el(
        'p',
        'Starts restricted and undated. You can add dates and Information after saving.',
        'caption',
      ),
      save,
      progress,
    );
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      save.disabled = true;
      progress.textContent = 'Creating…';
      try {
        await unwrap(
          await client.POST('/tenants/{tenant_id}/entities', {
            params: { path: { tenant_id: tenantId } },
            body: {
              id,
              name: name.input.value,
              kinds: [kind.value as 'event' | 'fact'],
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
          if (existing.data?.kinds.includes(kind.value as 'event' | 'fact')) {
            if (form.isConnected) location.assign(entryHref(tenantId, id));
            return;
          }
        } catch {
          /* Keep the stable retry identity and draft. */
        }
        progress.textContent = `${message(error)} Your draft is kept.`;
        save.disabled = false;
      }
    });
    create.append(form);
    host.append(create);
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
    status,
    list,
    nav,
  );
  showChoices();
  await load();
}
