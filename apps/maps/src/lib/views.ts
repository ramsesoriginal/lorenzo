import { client, fetchAllPages, type Schema, unwrap } from './api';
import { connectionsSection } from './connections-section';
import {
  actions,
  audienceBadge,
  backLink,
  button,
  card,
  claim,
  el,
  empty,
  errorNotice,
  field,
  groupTitle,
  icon,
  link,
  loading,
  locationHref,
  message,
  metaLine,
  pageHead,
  say,
  sectionHead,
  statusLine,
  submit,
} from './dom';
import { canManage, libraryName, myLibraries } from './names';
import { start } from './sign-in';

type Stub = Schema<'LocationStub'>;
type Place = Schema<'LocationOut'>;

const tenantOf = () => new URLSearchParams(location.search).get('tenant');

/** Libraries first: a person opens Locations from the library they are working in. */
export async function mountHome() {
  const host = document.querySelector<HTMLElement>('#maps-home');
  if (!host || !claim(host)) return;
  const me = await start();
  if (!me || !host.isConnected) return;
  try {
    host.replaceChildren(loading('Opening your libraries…'));
    const libraries = await myLibraries();
    const view = el('div', '', 'stack view');
    view.append(
      pageHead('Maps', { lede: 'The places of your libraries, from a whole world to one room.' }),
    );
    if (libraries.length) {
      const list = el('ul', '', 'list');
      for (const library of libraries) {
        const row = el('li');
        const text = el('div', '', 'stack-tight grow');
        text.append(
          link(library.name, `/locations/?${new URLSearchParams({ tenant: library.id })}`),
        );
        row.append(text, el('span', library.role, 'chip'));
        list.append(row);
      }
      view.append(list);
    } else view.append(empty('You are not in a library yet.'));
    host.replaceChildren(view);
  } catch (error) {
    host.querySelector('[data-loading]')?.remove();
    host.append(errorNotice(error));
  }
}

async function roots(tenant: string, q?: string) {
  return fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/locations', {
        params: {
          path: { tenant_id: tenant },
          query: q ? { q, page, size: 100 } : { root: true, page, size: 100 },
        },
      }),
    ),
  );
}

async function partsOf(tenant: string, id: string) {
  return fetchAllPages(async (page) =>
    unwrap(
      await client.GET('/tenants/{tenant_id}/locations/{location_id}/parts', {
        params: { path: { tenant_id: tenant, location_id: id }, query: { page, size: 100 } },
      }),
    ),
  );
}

/** One Location in a tree: its name as a link, and what is inside it when it is opened. */
function treeItem(tenant: string, stub: Stub) {
  const item = el('li', '', 'place-item');
  const row = el('div', '', 'place-row');
  const toggle = el('button', '', 'place-toggle');
  toggle.type = 'button';
  toggle.setAttribute('aria-expanded', 'false');
  toggle.setAttribute('aria-label', `Show what is inside ${stub.name}`);
  toggle.append(icon('next', 'icon panel-chevron'));
  const inside = el('ul', '', 'place-tree');
  inside.hidden = true;
  let loaded = false;
  toggle.addEventListener('click', () => {
    const open = toggle.getAttribute('aria-expanded') !== 'true';
    toggle.setAttribute('aria-expanded', String(open));
    inside.hidden = !open;
    if (!open || loaded) return;
    loaded = true;
    inside.replaceChildren(el('li', 'Opening…', 'status-text'));
    void partsOf(tenant, stub.id)
      .then((parts) => {
        inside.replaceChildren(
          ...(parts.length
            ? parts.map((part) => treeItem(tenant, part))
            : [el('li', 'Nothing inside yet.', 'status-text')]),
        );
      })
      .catch((error) => {
        loaded = false;
        inside.replaceChildren(errorNotice(error));
      });
  });
  row.append(
    toggle,
    icon('kind-location'),
    link(stub.name, locationHref(tenant, stub.id, stub.slug)),
  );
  const others = stub.kinds.filter((kind) => kind !== 'location');
  if (others.length) row.append(el('span', others.join(', ').replaceAll('_', ' '), 'chip'));
  item.append(row, inside);
  return item;
}

/** A form that makes a Location: a root, or a part of `parent`. */
function createForm(tenant: string, parent: string | null, onDone: (place: Place) => void) {
  const form = el('form', '', 'stack');
  const name = field('Name');
  name.input.required = true;
  const slug = field('Link name (optional)');
  const order = field('Stack order (optional)', '', 'number');
  order.input.step = 'any';
  const open = field('Visible to everyone in the library', '', 'checkbox');
  const status = statusLine();
  const save = submit('Add Location');
  const grid = el('div', '', 'grid');
  grid.style.setProperty('--grid-min', '240px');
  grid.append(name.label, slug.label, order.label);
  form.append(grid, open.label, actions(save), status);
  const id = crypto.randomUUID();
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    save.disabled = true;
    void (async () => {
      try {
        const place = await unwrap(
          await client.POST('/tenants/{tenant_id}/locations', {
            params: { path: { tenant_id: tenant } },
            body: {
              id,
              name: name.input.value,
              slug: slug.input.value || null,
              is_public: open.input.checked,
              parent_id: parent,
              level_ordinal: order.input.value || null,
            },
          }),
        );
        onDone(place);
      } catch (error) {
        say(status, `${message(error)} Your draft is still here.`, true);
        save.disabled = false;
      }
    })();
  });
  return form;
}

export async function mountLocations() {
  const host = document.querySelector<HTMLElement>('#maps-locations');
  if (!host || !claim(host)) return;
  const me = await start();
  const tenant = tenantOf();
  if (!me || !tenant || !host.isConnected) return;
  try {
    host.replaceChildren(loading('Opening Locations…'));
    const [name, manage] = await Promise.all([libraryName(tenant), canManage(tenant)]);
    const view = el('div', '', 'stack view');
    view.append(
      pageHead('Locations', {
        crumbs: [backLink('Libraries', '/')],
        lede: name ? `In ${name}.` : undefined,
      }),
    );
    const search = field('Find a Location');
    search.input.type = 'search';
    const list = el('ul', '', 'place-tree');
    const status = statusLine();
    let sequence = 0;
    async function show() {
      const mine = ++sequence;
      const query = search.input.value.trim();
      try {
        say(status, 'Opening…');
        const found = await roots(tenant as string, query || undefined);
        if (mine !== sequence) return;
        say(status, '');
        list.replaceChildren(
          ...(found.length
            ? found.map((stub) => treeItem(tenant as string, stub))
            : [
                el('li', query ? 'No Location has that name.' : 'No Locations yet.', 'status-text'),
              ]),
        );
      } catch (error) {
        if (mine === sequence) say(status, message(error), true);
      }
    }
    search.input.addEventListener('input', () => void show());
    const section = el('section', '', 'stack');
    section.append(sectionHead('Where things are'), search.label, status, list);
    view.append(section);
    if (manage) {
      const add = el('section', '', 'stack');
      add.append(
        sectionHead('Add a Location'),
        card(
          createForm(tenant, null, (place) =>
            location.assign(locationHref(tenant, place.id, place.slug)),
          ),
        ).root,
      );
      view.append(add);
    }
    host.replaceChildren(view);
    await show();
  } catch (error) {
    host.querySelector('[data-loading]')?.remove();
    host.append(errorNotice(error));
  }
}

/** The id of the entry the address names, by `id` or by link name. */
export async function resolveEntry(tenant: string, what = 'Location') {
  const params = new URLSearchParams(location.search);
  const id = params.get('id');
  if (id) return id;
  const slug = params.get('slug');
  if (!slug) throw new Error(`This address does not name a ${what}.`);
  const entry = await unwrap(
    await client.GET('/tenants/{tenant_id}/entities/by-slug/{slug}', {
      params: { path: { tenant_id: tenant, slug } },
    }),
  );
  return entry.id;
}

export async function mountLocation() {
  const host = document.querySelector<HTMLElement>('#maps-location');
  if (!host || !claim(host)) return;
  const me = await start();
  const tenant = tenantOf();
  if (!me || !tenant || !host.isConnected) return;
  const render = async () => {
    try {
      host.replaceChildren(loading('Opening this Location…'));
      const id = await resolveEntry(tenant);
      const result = await client.GET('/tenants/{tenant_id}/locations/{location_id}', {
        params: { path: { tenant_id: tenant, location_id: id } },
      });
      const place = await unwrap(result);
      const version = result.response.headers.get('etag') ?? '';
      const [name, parts] = await Promise.all([libraryName(tenant), partsOf(tenant, place.id)]);
      const view = el('div', '', 'stack view');
      const crumbs = [backLink('Locations', `/locations/?${new URLSearchParams({ tenant })}`)];
      if (place.within)
        crumbs.push(
          link(`In ${place.within.name}`, locationHref(tenant, place.within.id, place.within.slug)),
        );
      const meta: Node[] = [];
      if (name) meta.push(metaLine('kind-location', name));
      const others = place.kinds.filter((kind) => kind !== 'location');
      if (others.length) meta.push(el('span', others.join(', ').replaceAll('_', ' '), 'chip'));
      if (place.is_public !== null && place.is_public !== undefined)
        meta.push(
          audienceBadge(place.is_public ? 'Visible to everyone' : 'Restricted', place.is_public),
        );
      view.append(pageHead(place.name, { crumbs, meta }));
      const inside = el('section', '', 'stack');
      const list = el('ul', '', 'place-tree');
      list.append(
        ...(parts.length
          ? parts.map((part) => treeItem(tenant, part))
          : [el('li', 'Nothing inside yet.', 'status-text')]),
      );
      inside.append(sectionHead('Inside', { count: parts.length }), list);
      view.append(inside);
      view.append(
        await connectionsSection({
          tenant,
          place,
          writer: place.can_manage === true,
          again: render,
        }),
      );
      if (place.can_manage) view.append(manageSections(tenant, place, version, render));
      host.replaceChildren(view);
    } catch (error) {
      host.querySelector('[data-loading]')?.remove();
      host.replaceChildren(errorNotice(error));
    }
  };
  await render();
}

function manageSections(tenant: string, place: Place, version: string, again: () => Promise<void>) {
  const wrap = el('div', '', 'stack');
  const entity = { tenant_id: tenant, entity_id: place.id };

  // The name.
  const rename = el('form', '', 'stack');
  const name = field('Rename this Location', place.name);
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
            body: { name: name.input.value },
          }),
        );
        await again();
      } catch (error) {
        say(renameStatus, `${message(error)} Your change is still here.`, true);
      }
    })();
  });

  // Who sees it.
  const visibility = field('Everyone in the library can see this Location', '', 'checkbox');
  visibility.input.checked = place.is_public === true;
  const visibilityStatus = statusLine();
  const saveVisibility = button('Save visibility', async () => {
    const current = await client.GET('/tenants/{tenant_id}/entities/{entity_id}/audience', {
      params: { path: entity },
    });
    const audience = await unwrap(current);
    const saved = await client.PUT('/tenants/{tenant_id}/entities/{entity_id}/audience', {
      params: { path: entity },
      headers: { 'If-Match': current.response.headers.get('etag') ?? '' },
      body: { ...audience, is_public: visibility.input.checked },
    });
    await unwrap(saved);
    await again();
  });

  // Where it sits: in another Location, or on its own at the top.
  const parent = el('form', '', 'stack');
  const find = field('Move it into (type a name)');
  find.input.type = 'search';
  const choices = el('select', '', 'text-input');
  choices.setAttribute('aria-label', 'Locations that match');
  const order = field('Stack order (optional)', place.level_ordinal ?? '', 'number');
  order.input.step = 'any';
  const moveStatus = statusLine();
  const move = submit('Move here', 'secondary');
  move.disabled = true;
  let lookup = 0;
  find.input.addEventListener('input', () => {
    const mine = ++lookup;
    const query = find.input.value.trim();
    if (!query) {
      choices.replaceChildren();
      move.disabled = true;
      return;
    }
    void roots(tenant, query).then((found) => {
      if (mine !== lookup) return;
      choices.replaceChildren(
        ...found
          .filter((stub) => stub.id !== place.id)
          .map((stub) => {
            const option = el('option', stub.name);
            option.value = stub.id;
            return option;
          }),
      );
      move.disabled = choices.options.length === 0;
    });
  });
  parent.append(
    find.label,
    choices,
    order.label,
    actions(
      move,
      button(
        'Make it a top-level Location',
        async () => {
          await unwrap(
            await client.DELETE('/tenants/{tenant_id}/locations/{location_id}/part-of', {
              params: { path: { tenant_id: tenant, location_id: place.id } },
            }),
          );
          await again();
        },
        { variant: 'secondary' },
      ),
    ),
    moveStatus,
  );
  parent.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!choices.value) return;
    void (async () => {
      try {
        await unwrap(
          await client.PUT('/tenants/{tenant_id}/locations/{location_id}/part-of', {
            params: { path: { tenant_id: tenant, location_id: place.id } },
            body: { parent_entity_id: choices.value, level_ordinal: order.input.value || null },
          }),
        );
        await again();
      } catch (error) {
        say(moveStatus, message(error), true);
      }
    })();
  });

  const edit = el('section', '', 'stack');
  edit.append(
    sectionHead('Edit'),
    card(
      groupTitle('h3', 'Name'),
      rename,
      groupTitle('h3', 'Who can see it'),
      visibility.label,
      actions(saveVisibility),
      visibilityStatus,
      groupTitle('h3', 'Where it sits'),
      parent,
    ).root,
  );
  const add = el('section', '', 'stack');
  add.append(
    sectionHead('Add a Location inside'),
    card(
      createForm(tenant, place.id, (made) =>
        location.assign(locationHref(tenant, made.id, made.slug)),
      ),
    ).root,
  );
  wrap.append(add, edit);
  return wrap;
}
