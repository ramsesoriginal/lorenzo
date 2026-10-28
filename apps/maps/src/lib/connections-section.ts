// The connections of a Location (ADR 0365): where each goes, in words, and for those who write,
// joining it to another place and removing a connection. The API decides every write.
import { client, fetchAllPages, type Schema, unwrap } from './api';
import { seenFrom, wayWords } from './connection-words';
import {
  actions,
  card,
  el,
  empty,
  field,
  groupTitle,
  link,
  locationHref,
  message,
  say,
  sectionHead,
  select,
  statusLine,
  submit,
} from './dom';
import { findLocations } from './map-api';

type Connection = Schema<'ConnectionOut'>;

async function connectionsOf(tenant: string, end: string): Promise<Connection[]> {
  return fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/connections', {
        params: { path: { tenant_id: tenant }, query: { end, page, size: 100 } },
        cache: 'no-cache',
      }),
    ),
  );
}

export async function connectionsSection(context: {
  tenant: string;
  place: { id: string; name: string; is_public?: boolean | null };
  writer: boolean;
  again: () => Promise<void>;
}) {
  const { tenant, place, writer, again } = context;
  const section = el('section', '', 'stack');
  let found: Connection[] = [];
  try {
    found = await connectionsOf(tenant, place.id);
  } catch (error) {
    section.append(sectionHead('Connections'), el('p', message(error), 'error-text'));
    return section;
  }
  section.append(sectionHead('Connections', { count: found.length }));
  const list = el('ul', '', 'list map-connections');
  for (const connection of found) {
    const { way, other } = seenFrom(connection, place.id);
    const item = el('li');
    item.append(el('span', `${connection.name} `, 'place-name'));
    item.append(document.createTextNode(`${wayWords(way, '')}`.trimEnd() + ' '));
    item.append(
      other.kinds.includes('location')
        ? link(other.name, locationHref(tenant, other.id, other.slug))
        : document.createTextNode(other.name),
    );
    if (writer && connection.can_manage) {
      let sure = false;
      const remove = el('button', 'Remove', 'btn btn-secondary map-point-button');
      remove.type = 'button';
      remove.setAttribute('aria-label', `Remove ${connection.name}`);
      remove.addEventListener('click', () => {
        if (!sure) {
          sure = true;
          remove.textContent = 'Really remove?';
          remove.setAttribute('aria-label', `Really remove ${connection.name}?`);
          return;
        }
        remove.disabled = true;
        void (async () => {
          try {
            await client.DELETE('/tenants/{tenant_id}/entities/{entity_id}', {
              params: { path: { tenant_id: tenant, entity_id: connection.id } },
            });
            await again();
          } catch (error) {
            item.append(el('span', message(error), 'error-text'));
            remove.disabled = false;
          }
        })();
      });
      item.append(document.createTextNode(' '), remove);
    }
    list.append(item);
  }
  section.append(found.length ? list : empty('Nothing connects to this Location yet.'));
  if (!writer) return section;

  // Join this Location to another.
  const form = el('form', '', 'stack-tight');
  const search = field('Join it to (type a name)');
  search.input.type = 'search';
  const choices = el('select', '', 'text-input');
  choices.setAttribute('aria-label', 'Locations to join it to');
  const none = el('option', 'Choose a Location…');
  none.value = '';
  choices.append(none);
  let sequence = 0;
  search.input.addEventListener('input', () => {
    const mine = ++sequence;
    const query = search.input.value.trim();
    if (!query) return;
    void findLocations(tenant, query).then((places) => {
      if (mine !== sequence) return;
      choices.replaceChildren(
        none,
        ...places
          .filter((candidate) => candidate.id !== place.id)
          .map((candidate) => {
            const option = el('option', candidate.name);
            option.value = candidate.id;
            return option;
          }),
      );
    });
  });
  const name = field('Called');
  const oneWay = field('One way only', '', 'checkbox');
  const direction = select('The way goes', [
    ['from', 'From here'],
    ['to', 'To here'],
  ]);
  direction.label.hidden = true;
  oneWay.input.addEventListener('change', () => {
    direction.label.hidden = !oneWay.input.checked;
  });
  const open = field('Everyone in the library may see it', '', 'checkbox');
  open.input.checked = place.is_public === true;
  const status = statusLine();
  form.append(
    search.label,
    choices,
    name.label,
    oneWay.label,
    direction.label,
    open.label,
    actions(submit('Join', 'secondary')),
    status,
  );
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const otherId = choices.value;
    if (!otherId) {
      say(status, 'Choose the Location to join it to.', true);
      return;
    }
    const other = choices.selectedOptions[0]?.textContent ?? 'there';
    const leaves = !oneWay.input.checked || direction.input.value === 'from';
    void (async () => {
      try {
        await unwrap(
          await client.POST('/tenants/{tenant_id}/connections', {
            params: { path: { tenant_id: tenant } },
            body: {
              id: crypto.randomUUID(),
              name: name.input.value.trim() || `${place.name} - ${other}`,
              end_a: leaves ? place.id : otherId,
              end_b: leaves ? otherId : place.id,
              one_way: oneWay.input.checked,
              prototypes: [],
              is_public: open.input.checked,
            },
          }),
        );
        await again();
      } catch (error) {
        say(status, `${message(error)} Your draft is still here.`, true);
      }
    })();
  });
  section.append(card(groupTitle('h3', 'Join to another place'), form).root);
  return section;
}
