import { client, unwrap } from './api';

const node = <K extends keyof HTMLElementTagNameMap>(tag: K, text = '') => {
  const el = document.createElement(tag);
  el.textContent = text;
  return el;
};
const outline = async (tenant: string, id: string) =>
  unwrap(
    await client.GET('/tenants/{tenant_id}/writing/entries/{id}', {
      params: { path: { tenant_id: tenant, id } },
    }),
  );
type Outline = Awaited<ReturnType<typeof outline>>;

export function moveControls(
  tenant: string,
  id: string,
  name: string,
  source: Outline | undefined,
  done: () => Promise<void>,
) {
  const details = node('details');
  const summary = node('summary', 'Move');
  summary.setAttribute('aria-label', `Move: ${name}`);
  details.append(summary);
  const body = node('div');
  body.className = 'stack-tight';
  details.append(body);
  let loaded = false;
  details.addEventListener('toggle', () => {
    if (!details.open || loaded) return;
    loaded = true;
    const status = node('p');
    status.setAttribute('role', 'status');
    body.append(status);
    const report = (error: unknown) => {
      status.textContent =
        error instanceof Error ? error.message : 'This move could not be completed.';
    };
    const action = (label: string, run: () => Promise<void>) => {
      const button = node('button', label);
      button.type = 'button';
      button.className = 'btn btn-secondary';
      button.addEventListener('click', () => {
        button.disabled = true;
        void run()
          .catch(report)
          .finally(() => {
            button.disabled = false;
          });
      });
      return button;
    };
    void (async () => {
      const child = await outline(tenant, id);
      const origin =
        source ?? (child.parent_id ? await outline(tenant, child.parent_id) : undefined);
      const prepare = (target: Outline | undefined, position: HTMLSelectElement | undefined) => {
        let attempt: { id: string; before: string | null } | undefined;
        return async () => {
          const before = position?.value || null;
          if (!attempt || attempt.before !== before) attempt = { id: crypto.randomUUID(), before };
          status.textContent = 'Moving';
          await unwrap(
            await client.POST('/tenants/{tenant_id}/writing/entries/{id}/moves/{operation_id}', {
              params: {
                path: { tenant_id: tenant, id, operation_id: attempt.id },
                header: { 'if-match': child.version },
              },
              body: {
                source_parent_id: child.parent_id ?? null,
                destination_parent_id: target?.id ?? null,
                source_version: origin?.version ?? null,
                destination_version: target?.version ?? null,
                before_element_id: before,
              },
            }),
          );
          await done();
        };
      };
      if (child.parent_id) {
        body.append(action('Make unassigned', prepare(undefined, undefined)));
        if (origin?.parent_id) {
          const parent = await outline(tenant, origin.parent_id);
          body.append(action('Promote one level', prepare(parent, undefined)));
        }
      }
      const search = node('input');
      search.type = 'search';
      search.className = 'text-input';
      search.setAttribute('aria-label', `Destination for ${name}`);
      search.placeholder = 'Edition or Chapter title';
      const matches = node('div');
      matches.className = 'stack-tight';
      const selection = node('div');
      selection.className = 'stack-tight';
      body.append(
        search,
        action('Find destination', async () => {
          const found = await unwrap(
            await client.GET('/tenants/{tenant_id}/entities', {
              params: {
                path: { tenant_id: tenant },
                query: { kind: ['edition', 'chapter'], q: search.value.trim(), size: 10 },
              },
            }),
          );
          matches.replaceChildren();
          selection.replaceChildren();
          for (const candidate of found.items) {
            if (candidate.id === id || candidate.id === child.parent_id) continue;
            matches.append(
              action(candidate.name, async () => {
                const target = await outline(tenant, candidate.id);
                selection.replaceChildren(node('p', `Move into ${target.name}`));
                const position = node('select');
                position.setAttribute('aria-label', 'Move position');
                const end = node('option', 'At the end');
                end.value = '';
                position.append(end);
                for (const [index, item] of target.elements.entries()) {
                  const option = node(
                    'option',
                    `Before ${item.name ?? `text or picture ${index + 1}`}`,
                  );
                  option.value = item.id;
                  position.append(option);
                }
                selection.append(position, action('Move here', prepare(target, position)));
              }),
            );
          }
          if (!matches.children.length)
            matches.append(node('p', 'No matching destinations. Try another title.'));
          if (found.total > 10)
            matches.append(node('p', 'Refine the title to find more destinations.'));
        }),
        matches,
        selection,
      );
    })().catch(report);
  });
  return details;
}
