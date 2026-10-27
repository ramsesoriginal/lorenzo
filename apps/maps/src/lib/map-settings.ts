// Making a Map and setting it up (ADR 0353): what the sheet is, what it shows, how it is drawn by
// default and who may see it. The API decides every write; a refusal is shown as it is given.
import { client, unwrap } from './api';
import {
  actions,
  button,
  card,
  el,
  field,
  groupTitle,
  message,
  say,
  select,
  statusLine,
  submit,
} from './dom';
import { findLocations, type Header } from './map-api';

const FORMAT = 'lorenzo.map-system/1';

const KINDS: [string, string][] = [
  ['plane', 'A plane, with its own units'],
  ['outline', 'An outline, with no measure'],
];

const THEMES: [string, string][] = [
  ['', 'The default'],
  ['default', 'Default'],
  ['plain', 'Plain'],
];

type System = {
  format?: string;
  kind?: string;
  extent?: number[];
  scale?: { per_unit: number; unit: string };
};

/** The fields that say what a sheet is, and a way to read them as the system document. */
export function systemFields(current?: System) {
  const kind = select('The sheet is', KINDS, current?.kind ?? 'plane');
  const extent = current?.extent ?? [0, 0, 1000, 800];
  const width = field('Width', String((extent[2] ?? 1000) - (extent[0] ?? 0)), 'number');
  const height = field('Height', String((extent[3] ?? 800) - (extent[1] ?? 0)), 'number');
  for (const input of [width.input, height.input]) {
    input.min = '1';
    input.step = 'any';
    input.required = true;
  }
  const unit = field('Unit (optional)', current?.scale?.unit ?? '');
  const per = field(
    'How many of it one unit of the sheet is',
    String(current?.scale?.per_unit ?? ''),
    'number',
  );
  per.input.step = 'any';
  per.input.min = '0';
  const grid = el('div', '', 'grid');
  grid.style.setProperty('--grid-min', '200px');
  grid.append(kind.label, width.label, height.label, unit.label, per.label);

  function read(): System {
    const w = Number(width.input.value);
    const h = Number(height.input.value);
    if (!(w > 0) || !(h > 0)) throw new Error('The width and the height must be more than zero.');
    const x0 = extent[0] ?? 0;
    const y0 = extent[1] ?? 0;
    const system: System = {
      format: FORMAT,
      kind: kind.input.value,
      extent: [x0, y0, x0 + w, y0 + h],
    };
    if (kind.input.value === 'plane' && unit.input.value.trim()) {
      const amount = Number(per.input.value || 1);
      if (!(amount > 0))
        throw new Error('One unit of the sheet must be more than zero of the unit.');
      system.scale = { per_unit: amount, unit: unit.input.value.trim() };
    }
    return system;
  }
  return { grid, read };
}

/** *Make a Map*: for the library page of those who may write. */
export function makeMapForm(tenant: string, onMade: (id: string, slug: string | null) => void) {
  const form = el('form', '', 'stack');
  const name = field('Name');
  name.input.required = true;
  const open = field('Everyone in the library may see it', '', 'checkbox');
  const sheet = systemFields();
  const status = statusLine();
  const save = submit('Make the Map');
  form.append(name.label, sheet.grid, open.label, actions(save), status);
  const id = crypto.randomUUID();
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    save.disabled = true;
    void (async () => {
      try {
        const made = await unwrap(
          await client.POST('/tenants/{tenant_id}/maps', {
            params: { path: { tenant_id: tenant } },
            body: {
              id,
              name: name.input.value.trim(),
              system: sheet.read() as Record<string, unknown>,
              is_public: open.input.checked,
            },
          }),
        );
        onMade(made.id, made.slug ?? null);
      } catch (error) {
        say(status, `${message(error)} Your draft is still here.`, true);
        save.disabled = false;
      }
    })();
  });
  return card(form).root;
}

/** *Settings* of one Map, for those who may write: name, sheet, subject, theme and who sees it. */
export function settingsSection(
  tenant: string,
  header: Header,
  version: string,
  again: () => Promise<void>,
) {
  const entity = { tenant_id: tenant, entity_id: header.id };
  const wrap = el('div', '', 'stack');

  // The name.
  const rename = el('form', '', 'stack-tight');
  const name = field('Name', header.name);
  name.input.required = true;
  const renameStatus = statusLine();
  rename.append(name.label, actions(submit('Save name', 'secondary')), renameStatus);
  rename.addEventListener('submit', (event) => {
    event.preventDefault();
    void (async () => {
      try {
        await unwrap(
          await client.PATCH('/tenants/{tenant_id}/entities/{entity_id}', {
            params: { path: entity },
            headers: { 'If-Match': version },
            body: { name: name.input.value.trim() },
          }),
        );
        await again();
      } catch (error) {
        say(renameStatus, `${message(error)} Your change is still here.`, true);
      }
    })();
  });

  // The sheet, the Location it shows and the default look: one replace of the Map.
  const form = el('form', '', 'stack');
  const sheet = systemFields(header.system as System);
  const theme = select('How it is drawn unless a viewer chooses', THEMES, header.theme_hint ?? '');
  const find = field('The Location it shows (type a name)');
  find.input.type = 'search';
  const choices = el('select', '', 'text-input');
  choices.setAttribute('aria-label', 'Locations that match');
  const none = el('option', 'No Location');
  none.value = '';
  choices.append(none);
  if (header.subject) {
    const current = el('option', header.subject.name);
    current.value = header.subject.id;
    choices.append(current);
    choices.value = header.subject.id;
  }
  let sequence = 0;
  find.input.addEventListener('input', () => {
    const mine = ++sequence;
    const query = find.input.value.trim();
    if (!query) return;
    void findLocations(tenant, query).then((found) => {
      if (mine !== sequence) return;
      const keep = choices.value;
      choices.replaceChildren(
        none,
        ...found.map((place) => {
          const option = el('option', place.name);
          option.value = place.id;
          return option;
        }),
      );
      choices.value = found.some((place) => place.id === keep) ? keep : '';
    });
  });
  const settingsStatus = statusLine();
  form.append(
    sheet.grid,
    find.label,
    choices,
    theme.label,
    actions(submit('Save settings', 'secondary')),
    settingsStatus,
  );
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    void (async () => {
      try {
        await unwrap(
          await client.PUT('/tenants/{tenant_id}/maps/{map_id}', {
            params: { path: { tenant_id: tenant, map_id: header.id } },
            headers: { 'If-Match': version },
            body: {
              system: sheet.read() as Record<string, unknown>,
              subject_entity_id: choices.value || null,
              theme_hint: theme.input.value || null,
            },
          }),
        );
        await again();
      } catch (error) {
        say(settingsStatus, `${message(error)} Your change is still here.`, true);
      }
    })();
  });

  // Who sees it.
  const visibility = field('Everyone in the library can see this Map', '', 'checkbox');
  visibility.input.checked = header.is_public === true;
  const visibilityStatus = statusLine();
  const saveVisibility = button('Save visibility', async () => {
    const current = await client.GET('/tenants/{tenant_id}/entities/{entity_id}/audience', {
      params: { path: entity },
    });
    const audience = await unwrap(current);
    await unwrap(
      await client.PUT('/tenants/{tenant_id}/entities/{entity_id}/audience', {
        params: { path: entity },
        headers: { 'If-Match': current.response.headers.get('etag') ?? '' },
        body: { ...audience, is_public: visibility.input.checked },
      }),
    );
    await again();
  });

  wrap.append(
    card(
      groupTitle('h3', 'Name'),
      rename,
      groupTitle('h3', 'The sheet and how it is drawn'),
      form,
      groupTitle('h3', 'Who can see it'),
      visibility.label,
      actions(saveVisibility),
      visibilityStatus,
    ).root,
  );
  return wrap;
}
