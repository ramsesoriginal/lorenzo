import { client, unwrap } from './api';
import { outlineOf, writingAddress } from './composition';

const node = <K extends keyof HTMLElementTagNameMap>(tag: K, text = '') => {
  const el = document.createElement(tag);
  el.textContent = text;
  return el;
};

export async function carrierOutline(
  host: HTMLElement,
  tenant: string,
  current: Awaited<ReturnType<typeof outlineOf>>,
  refresh: () => Promise<void>,
) {
  const status = node('p');
  status.setAttribute('role', 'status');
  host.append(status);
  const action = (label: string, run: () => Promise<void>) => {
    const b = node('button', label);
    b.type = 'button';
    b.className = 'btn btn-secondary';
    b.addEventListener('click', () => {
      b.disabled = true;
      void run()
        .catch((error: unknown) => {
          status.textContent = error instanceof Error ? error.message : 'This could not be saved.';
        })
        .finally(() => {
          b.disabled = false;
        });
    });
    return b;
  };
  const own = await unwrap(
    await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
      params: { path: { tenant_id: tenant, entity_id: current.id } },
    }),
  );
  const payloads = new Map(
    own.information
      .filter((i) => i.type === 'manuscript')
      .flatMap((i) => i.payloads)
      .map((p) => [p.id, p]),
  );
  const ordered = current.elements.map((el) => ({
    id: el.id,
    target_entity_id: el.kind === 'coverage' && !el.payload_id ? el.target_id : null,
    target_payload_id: el.kind === 'coverage' ? el.payload_id : null,
  }));
  const save = async (elements: typeof ordered) => {
    await unwrap(
      await client.PUT('/tenants/{tenant_id}/writing/carriers/{id}/coverage', {
        params: {
          path: { tenant_id: tenant, id: current.id },
          header: { 'if-match': current.version },
        },
        body: { elements },
      }),
    );
    await refresh();
  };
  for (const [index, el] of current.elements.entries()) {
    const row = node('div');
    row.className = 'stack-tight';
    const p = payloads.get(el.id);
    const label =
      el.kind === 'coverage'
        ? `${el.name}${el.payload_id ? ' · selected block' : ''}`
        : p?.kind === 'description'
          ? p.content.slice(0, 80) || 'Empty text'
          : 'Picture';
    if (el.target_id) {
      const a = node('a', label);
      a.href = writingAddress(tenant, el.target_id);
      row.append(a);
    } else row.append(node('p', label));
    const controls = node('div');
    controls.className = 'row';
    for (const [title, offset] of [
      ['Up', -1],
      ['Down', 1],
    ] as const) {
      const button = action(title, async () => {
        const next = [...ordered];
        [next[index], next[index + offset]] = [next[index + offset], next[index]];
        await save(next);
      });
      button.disabled = index + offset < 0 || index + offset >= ordered.length;
      controls.append(button);
    }
    if (el.kind === 'coverage')
      controls.append(
        action('Remove coverage', () => save(ordered.filter((item) => item.id !== el.id))),
      );
    row.append(controls);
    host.append(row);
  }
  const search = (
    title: string,
    kinds: ('carrier' | 'edition' | 'chapter' | 'scene' | 'scene_telling')[],
    choose: (id: string, results: HTMLElement) => Promise<void>,
    container: HTMLElement = host,
  ) => {
    const details = node('details');
    details.append(node('summary', title));
    const input = node('input');
    input.type = 'search';
    input.className = 'text-input';
    input.setAttribute('aria-label', title);
    const results = node('div');
    results.className = 'stack-tight';
    details.append(
      input,
      action(`Find ${title.toLowerCase()}`, async () => {
        const found = await unwrap(
          await client.GET('/tenants/{tenant_id}/entities', {
            params: {
              path: { tenant_id: tenant },
              query: { kind: kinds, q: input.value.trim(), size: 10 },
            },
          }),
        );
        results.replaceChildren();
        for (const item of found.items.filter((item) => item.id !== current.id))
          results.append(action(item.name, () => choose(item.id, results)));
        if (!found.items.length) results.append(node('p', 'No matching entries.'));
        if (found.total > 10) results.append(node('p', 'Refine the title to find more entries.'));
      }),
      results,
    );
    container.append(details);
  };
  search(
    'Covered writing',
    ['edition', 'chapter', 'scene', 'scene_telling'],
    async (id, results) => {
      const outline = await outlineOf(tenant, id);
      const entry = await unwrap(
        await client.GET('/tenants/{tenant_id}/entities/{entity_id}', {
          params: { path: { tenant_id: tenant, entity_id: outline.manuscript_source_id ?? id } },
        }),
      );
      results.replaceChildren(node('p', outline.name));
      const occurrence = crypto.randomUUID();
      results.append(
        action('Include whole writing', () =>
          save([...ordered, { id: occurrence, target_entity_id: id, target_payload_id: null }]),
        ),
      );
      for (const payload of entry.information
        .filter((i) => i.type === 'manuscript')
        .flatMap((i) => i.payloads)) {
        if (!outline.elements.some((el) => el.id === payload.id && el.kind === 'payload')) continue;
        const title =
          payload.kind === 'description' ? payload.content.slice(0, 80) || 'Empty text' : 'Picture';
        const blockId = crypto.randomUUID();
        results.append(
          action(`Include block: ${title}`, () =>
            save([
              ...ordered,
              { id: blockId, target_entity_id: null, target_payload_id: payload.id },
            ]),
          ),
        );
      }
    },
  );
  const parents = own.prototypes.map((parent) => parent.id);
  const changeParents = async (parent_ids: string[]) => {
    await unwrap(
      await client.PUT('/tenants/{tenant_id}/writing/carriers/{id}/parents', {
        params: {
          path: { tenant_id: tenant, id: current.id },
          header: { 'if-match': current.version },
        },
        body: { parent_ids },
      }),
    );
    await refresh();
  };
  const parentList = node('details');
  parentList.append(node('summary', 'Carrier form'));
  parentList.append(
    node(
      'p',
      'Choose the Carrier prototypes this form or artifact inherits from. Writing and coverage stay its own.',
    ),
  );
  for (const parent of own.prototypes) {
    const row = node('div');
    row.className = 'row';
    const a = node('a', parent.name);
    a.href = writingAddress(tenant, parent.id);
    row.append(
      a,
      action(`Remove ${parent.name}`, () =>
        changeParents(parents.filter((id) => id !== parent.id)),
      ),
    );
    parentList.append(row);
  }
  host.append(parentList);
  search(
    'Carrier prototypes',
    ['carrier'],
    async (id) => changeParents([...new Set([...parents, id])]),
    parentList,
  );
}
